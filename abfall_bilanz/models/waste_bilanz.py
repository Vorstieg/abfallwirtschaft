# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, date
import base64
from ..library.parser import (
    create_waste_handling_notification_xml, 
    WasteMovementLocation, 
    Party, 
    SpecifiedLocation, 
    WasteMovementSite, 
    WasteHandlingNotification,
    Address,
    StoredMaterial,
    StorageState,
    CorrectionMaterial,
    StorageCorrection,
    WasteReclassification as ParserWasteReclassification,
    RemainingCapacity
)
from .edm_validator import EDMValidator

class WasteBilanz(models.TransientModel):
    _name = 'waste.bilanz'
    _description = 'Waste Balance Export Wizard'

    def _get_year_selection(self):
        current_year = datetime.now().year
        year_list = []
        for year in range(current_year - 10, current_year + 11):
            year_list.append((str(year), str(year)))
        return year_list

    year = fields.Selection(
        selection=_get_year_selection,
        string='Year',
        default=str(datetime.now().year),
        required=True
    )
    is_empty_report = fields.Boolean(string='Empty Report (Leermeldung)', 
                                    help="Check this if no waste movements or treatments occurred in the reporting year.")
    compliance_errors = fields.Text(string='Compliance Errors', readonly=True)

    def action_check_compliance(self):
        """Action for the 'Verify Data' button"""
        self.ensure_one()
        errors = self._get_compliance_errors()
        if not errors:
            self.compliance_errors = "Success: All records are compliant for this period."
        else:
            self.compliance_errors = "\n".join(errors)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_generate_report(self):
        self.ensure_one()
        errors = self._get_compliance_errors()
        if errors:
            self.compliance_errors = "\n".join(errors)
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        filename = f"Abfallbilanz_{self.year}_{'Empty' if self.is_empty_report else 'Full'}.xml"
        submission = self.env['waste.bilanz.submission'].create({
            'name': filename,
            'year': str(self.year),
            'is_empty_report': self.is_empty_report,
            'company_id': self.env.company.id,
            'state': 'generated'
        })
        submission.generate_xml_data()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'waste.bilanz.submission',
            'res_id': submission.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_compliance_errors(self):
        """Collects all compliance errors for the selected year"""
        start_date = datetime(int(self.year), 1, 1)
        end_date = datetime(int(self.year), 12, 31, 23, 59, 59)
        errors = []

        # 1. Company Check
        company = self.env.company
        if not company.partner_id.person_gln:
            errors.append(f"Company {company.name}: Missing Person GLN.")

        # 2. Waste Activity Check (Mutually exclusive with Empty Report)
        moves = self.env['waste.move'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', '=', 'approved'),
            ('company_id', '=', company.id),
        ])
        states = self.env['waste.storage.state'].search([
            ('reporting_date', '>=', start_date.date()),
            ('reporting_date', '<=', end_date.date()),
            ('company_id', '=', company.id),
        ])
        corrections = self.env['waste.storage.correction'].search([
            ('reporting_date', '>=', start_date.date()),
            ('reporting_date', '<=', end_date.date()),
            ('company_id', '=', company.id),
        ])
        reclasses = self.env['waste.reclassification'].search([
            ('reporting_date', '>=', start_date.date()),
            ('reporting_date', '<=', end_date.date()),
            ('company_id', '=', company.id),
        ])
        capacities = self.env['waste.remaining.capacity'].search([
            ('reporting_date', '>=', start_date.date()),
            ('reporting_date', '<=', end_date.date()),
            ('company_id', '=', company.id),
        ])

        has_data = moves or states or corrections or reclasses or capacities

        if self.is_empty_report:
            if has_data:
                errors.append("Empty Report error: Found approved waste activities or storage entries for this year. "
                              "A Leermeldung is only allowed if no activities occurred.")
            return errors # No further checks needed for empty report

        if not has_data:
            errors.append("No data found for this year. Did you mean to file an 'Empty Report'?")
            return errors

        # 3. Detailed Data Integrity Checks (only if not empty report)
        for move in moves:
            if move.amount <= 0:
                errors.append(f"Move {move.name or move.id}: Amount must be greater than zero.")
            if not move.abfallart:
                errors.append(f"Move {move.name or move.id}: Missing Waste Type.")
            if not move.origin_partner:
                errors.append(f"Move {move.name or move.id}: Missing Origin Partner.")
            if not move.recipient_partner:
                errors.append(f"Move {move.name or move.id}: Missing Recipient Partner.")
            
            # Party specific checks
            for partner, label in [(move.origin_partner, "Origin"), (move.recipient_partner, "Recipient")]:
                if partner and not partner.person_gln:
                    if not (partner.city or partner.zip or partner.street or partner.country_id):
                        errors.append(f"Move {move.name or move.id}: {label} Partner '{partner.name}' is non-registered but has incomplete address.")

        for s in states:
            if s.amount < 0:
                errors.append(f"Storage State {s.id}: Amount cannot be negative.")
            if not s.installation_id.gtin:
                errors.append(f"Storage State {s.id}: Installation missing GTIN.")

        for c in corrections:
            if c.amount == 0:
                errors.append(f"Correction {c.id}: Amount cannot be zero.")
            if not c.installation_id.gtin:
                errors.append(f"Correction {c.id}: Installation missing GTIN.")

        for r in reclasses:
            if r.amount <= 0:
                errors.append(f"Reclassification {r.id}: Amount must be positive.")
            if not r.reclassification_reason_id:
                errors.append(f"Reclassification {r.id}: Missing Reason.")

        # 4. Inventory Reconciliation (Consistency Check)
        # Verify that reported states match the calculated balance
        for inst in self.env['waste.treatment.installation'].search([('treatment_site_id.partner_id', '=', company.partner_id.id)]):
            # Find all waste types that have a storage state or activity at this installation
            active_waste_types = states.filtered(lambda s: s.installation_id == inst).mapped('abfallart')
            active_waste_types |= moves.filtered(lambda m: m.origin_installation == inst or m.recipient_installation == inst).mapped('abfallart')
            
            for w_type in active_waste_types:
                prev_stock = self._get_previous_inventory(inst, w_type, int(self.year))
                
                # Movements
                inst_moves_in = moves.filtered(lambda m: m.recipient_installation == inst and m.abfallart == w_type)
                inst_moves_out = moves.filtered(lambda m: m.origin_installation == inst and m.abfallart == w_type)
                balance_moves = sum(inst_moves_in.mapped('amount')) - sum(inst_moves_out.mapped('amount'))
                
                # Corrections
                inst_corrections = corrections.filtered(lambda c: c.installation_id == inst and c.abfallart == w_type)
                balance_corrections = sum(inst_corrections.mapped('amount'))
                
                # Reclassifications
                inst_reclasses_in = reclasses.filtered(lambda r: r.installation_id == inst and r.new_abfallart == w_type)
                inst_reclasses_out = reclasses.filtered(lambda r: r.installation_id == inst and r.preliminary_abfallart == w_type)
                balance_reclasses = sum(inst_reclasses_in.mapped('amount')) - sum(inst_reclasses_out.mapped('amount'))
                
                expected_stock = prev_stock + balance_moves + balance_corrections + balance_reclasses
                
                # Actual reported stock (must be approved to count)
                actual_state = states.filtered(lambda s: s.installation_id == inst and s.abfallart == w_type and s.state == 'approved')
                actual_stock = sum(actual_state.mapped('amount'))
                
                if abs(expected_stock - actual_stock) > 0.001: # Use epsilon for float comparison
                    errors.append(f"Consistency Error [{inst.name} - {w_type.name}]: "
                                  f"Calculated stock is {expected_stock:.2f} kg, but reported approved stock is {actual_stock:.2f} kg. "
                                  f"Difference: {expected_stock - actual_stock:.2f} kg.")

        return errors

    def action_calculate_inventory(self):
        """
        Calculates the end-of-year inventory for all installations and waste types.
        Formula: Previous Inventory + Takeovers - Handovers + Corrections + Reclassifications
        """
        self.ensure_one()
        year_int = int(self.year)
        start_date = datetime(year_int, 1, 1)
        end_date = datetime(year_int, 12, 31, 23, 59, 59)
        reporting_date = end_date.date()

        # Find the specific mandated quantification type (GTIN: 9008390100011)
        quant_type = self.env['waste.quantification.type'].search([('gtin', '=', '9008390100011')], limit=1)
        if not quant_type:
             raise UserError("Mandatory Waste Quantification Type (GTIN: 9008390100011) not found in the system. Please ensure it is created.")

        # Get installations for this company
        installations = self.env['waste.treatment.installation'].search([('treatment_site_id.partner_id', '=', self.env.company.partner_id.id)])
        
        # Get all waste types handling in the system
        waste_types = self.env['waste.type'].search([])

        for inst in installations:
            for w_type in waste_types:
                # 1. Starting Balance (Last approved state before this year)
                starting_balance = self._get_previous_inventory(inst, w_type, year_int)
                
                # 2. Takeovers (Moving to this installation)
                takeovers = self.env['waste.move'].search([
                    ('recipient_installation', '=', inst.id),
                    ('abfallart', '=', w_type.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('state', '=', 'approved'),
                    ('company_id', '=', self.env.company.id),
                ])
                takeover_amount = sum(takeovers.mapped('amount'))

                # 3. Handovers (Moving from this installation)
                handovers = self.env['waste.move'].search([
                    ('origin_installation', '=', inst.id),
                    ('abfallart', '=', w_type.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('state', '=', 'approved'),
                    ('company_id', '=', self.env.company.id),
                ])
                handover_amount = sum(handovers.mapped('amount'))

                # 4. Corrections
                corrections = self.env['waste.storage.correction'].search([
                    ('installation_id', '=', inst.id),
                    ('abfallart', '=', w_type.id),
                    ('reporting_date', '>=', start_date.date()),
                    ('reporting_date', '<=', end_date.date()),
                    ('company_id', '=', self.env.company.id),
                ])
                correction_amount = sum(corrections.mapped('amount'))

                # 5. Reclassifications (Incoming/Outgoing)
                # Incoming (where this type is the 'new' type)
                reclasses_in = self.env['waste.reclassification'].search([
                    ('installation_id', '=', inst.id),
                    ('new_abfallart', '=', w_type.id),
                    ('reporting_date', '>=', start_date.date()),
                    ('reporting_date', '<=', end_date.date()),
                    ('company_id', '=', self.env.company.id),
                ])
                reclass_in_amount = sum(reclasses_in.mapped('amount'))

                # Outgoing (where this type is the 'original' type)
                reclasses_out = self.env['waste.reclassification'].search([
                    ('installation_id', '=', inst.id),
                    ('preliminary_abfallart', '=', w_type.id),
                    ('reporting_date', '>=', start_date.date()),
                    ('reporting_date', '<=', end_date.date()),
                    ('company_id', '=', self.env.company.id),
                ])
                reclass_out_amount = sum(reclasses_out.mapped('amount'))

                # Final Calculation
                total_amount = (starting_balance + takeover_amount - handover_amount + 
                                correction_amount + reclass_in_amount - reclass_out_amount)

                # Only create if there's an actual inventory or movements happened
                if total_amount != 0 or takeover_amount or handover_amount or correction_amount:
                    # Check if a state already exists for this date/inst/type
                    existing = self.env['waste.storage.state'].search([
                        ('installation_id', '=', inst.id),
                        ('abfallart', '=', w_type.id),
                        ('reporting_date', '=', reporting_date),
                        ('company_id', '=', self.env.company.id),
                    ])
                    if not existing:
                        self.env['waste.storage.state'].create({
                            'installation_id': inst.id,
                            'abfallart': w_type.id,
                            'reporting_date': reporting_date,
                            'amount': total_amount,
                            'quantification_type': quant_type.id,
                            'company_id': self.env.company.id,
                            'state': 'draft'
                        })
                    else:
                        # Update existing draft
                        existing.filtered(lambda s: s.state == 'draft').write({
                            'amount': total_amount
                        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Calculated Storage States',
            'res_model': 'waste.storage.state',
            'view_mode': 'list,form',
            'domain': [('reporting_date', '=', reporting_date), ('state', '=', 'draft')],
            'target': 'current',
        }

    def _get_previous_inventory(self, installation, waste_type, year):
        """Finds the most recent approved inventory before the given year"""
        prev_state = self.env['waste.storage.state'].search([
            ('installation_id', '=', installation.id),
            ('abfallart', '=', waste_type.id),
            ('reporting_date', '<', date(year, 1, 1)),
            ('state', '=', 'approved'),
            ('company_id', '=', self.env.company.id)
        ], order='reporting_date desc', limit=1)
        
        return prev_state.amount if prev_state else 0.0

class WasteBilanzSubmission(models.Model):
    _name = 'waste.bilanz.submission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Waste Balance Submission History'
    _order = 'submission_date desc'

    name = fields.Char(string='Report Name', required=True)
    year = fields.Char(string='Reporting Year', required=True)
    is_empty_report = fields.Boolean(string='Empty Report')
    xml_file = fields.Binary(string='XML File')
    xml_filename = fields.Char(string='XML Filename')
    submission_date = fields.Datetime(string='Submission/Generation Date', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Generated By', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    state = fields.Selection([
        ('generated', 'Generated'),
        ('submitted', 'Submitted to EDM'),
        ('error', 'Error')
    ], string='Status', default='generated')

    validation_results_html = fields.Html(string='EDM Validation Results', readonly=True)
    critical_count = fields.Integer(string='Critical Issues', readonly=True)
    error_count = fields.Integer(string='Error Issues', readonly=True)
    warning_count = fields.Integer(string='Warning Issues', readonly=True)
    hint_count = fields.Integer(string='Hint Issues', readonly=True)

    def action_validate_edm(self):
        self.ensure_one()
        validator = EDMValidator(self.env)
        result = validator.validate_submission(self)
        
        self.write({
            'validation_results_html': result.to_html(),
            'critical_count': result.critical_count,
            'error_count': result.error_count,
            'warning_count': result.warning_count,
            'hint_count': result.hint_count,
        })
        return True

    def action_download_bilanz(self):
        self.ensure_one()
        if not self.xml_file:
            self.generate_xml_data()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=waste.bilanz.submission&id={self.id}&field=xml_file&filename_field=xml_filename&download=true',
            'target': 'self',
        }

    @api.model
    def action_open_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Waste Balance'),
            'res_model': 'waste.bilanz',
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def generate_xml_data(self):
        self.ensure_one()
        # Run validation first (but don't block)
        self.action_validate_edm()
        
        year = int(self.year)
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        company = self.company_id or self.env.company

        # 1. Fetch Company Settings
        company_partner = company.partner_id
        obligated_party_gln = company_partner.person_gln

        if not obligated_party_gln:
            raise UserError(f"The company {company.name} (Partner: {company_partner.name}) has no Person GLN set! Please configure it in the contact details.")

        if self.is_empty_report:
            data = create_waste_handling_notification_xml(
                start_date, 
                end_date, 
                obligated_party_gln, 
                [],
                is_empty_report=True
            )
        else:
            # Fetch Data
            moves = self.env['waste.move'].search([
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('state', '=', 'approved'),
                ('company_id', '=', company.id),
            ])
            storage_states = self.env['waste.storage.state'].search([
                ('reporting_date', '>=', start_date),
                ('reporting_date', '<=', end_date),
                ('company_id', '=', company.id),
            ])
            storage_corrections = self.env['waste.storage.correction'].search([
                ('reporting_date', '>=', start_date),
                ('reporting_date', '<=', end_date),
                ('company_id', '=', company.id),
            ])
            reclassifications = self.env['waste.reclassification'].search([
                ('reporting_date', '>=', start_date),
                ('reporting_date', '<=', end_date),
                ('company_id', '=', company.id),
            ])
            remaining_capacities = self.env['waste.remaining.capacity'].search([
                ('reporting_date', '>=', start_date),
                ('reporting_date', '<=', end_date),
                ('company_id', '=', company.id),
            ])

            if not any([moves, storage_states, storage_corrections, reclassifications, remaining_capacities]):
                raise UserError(f"No relevant data found for Abfallbilanz {year}.")

            # Map Data
            mapped_moves = []
            for move in moves:
                self._validate_move(move)
                mapped_moves.append(self.map_move(move))

            mapped_states = [self.map_storage_state(s) for s in storage_states]
            mapped_corrections = [self.map_storage_correction(c) for c in storage_corrections]
            mapped_reclassifications = [self.map_reclassification(r) for r in reclassifications]
            mapped_capacities = [self.map_remaining_capacity(c) for c in remaining_capacities]

            data = create_waste_handling_notification_xml(
                start_date, 
                end_date, 
                obligated_party_gln, 
                mapped_moves,
                storage_states=mapped_states,
                storage_corrections=mapped_corrections,
                waste_reclassifications=mapped_reclassifications,
                remaining_capacities=mapped_capacities
            )

        self.write({
            'xml_file': base64.b64encode(data.encode('utf-8')),
            'xml_filename': f"Abfallbilanz_{self.year}_{'Empty' if self.is_empty_report else 'Full'}.xml",
            'state': 'generated'
        })
        return data

    def _validate_move(self, move):
        if not move.origin_partner:
            raise UserError(f"Origin Partner is missing for waste move {move.name}.")
        if not move.recipient_partner:
            raise UserError(f"Recipient Partner is missing for waste move {move.name}.")
        if not move.abfallart:
            raise UserError(f"Waste Type (Abfallart) is missing for waste move {move.name}.")
        
    def _map_address(self, partner):
        if not partner:
            return None
        return Address(
            # Odoo 'base' doesn't have numeric ISO code by default in res.country. 
            # Defaulting to "040" for at or using code if it's 3-digit.
            country_id="040" if partner.country_id and partner.country_id.code == 'AT' else (partner.country_id.code if partner.country_id else "040"), 
            city_name=partner.city,
            postcode=partner.zip,
            street_name=partner.street,
            building_number=partner.street2
        )

    def _map_party(self, partner):
        if not partner:
            return None
        address = None
        if not partner.person_gln:
            address = self._map_address(partner)
        return Party(
            id=partner.person_gln,
            name=partner.name,
            office_address=address
        )

    def map_move(self, move):
        origin_party = self._map_party(move.origin_partner)
        takeover_party = self._map_party(move.recipient_partner)
        handover_loc = WasteMovementLocation(
            origin_party,
            SpecifiedLocation(
                WasteMovementSite(move.origin_site.gtin, move.origin_site.name) if move.origin_site else None,
                WasteMovementSite(move.origin_installation.gtin, move.origin_installation.name) if move.origin_installation else None
            ),
            move.origin_type.gtin
        )
        takeover_loc = WasteMovementLocation(
            takeover_party,
            SpecifiedLocation(
                WasteMovementSite(move.recipient_site.gtin, move.recipient_site.name) if move.recipient_site else None,
                WasteMovementSite(move.recipient_installation.gtin, move.recipient_installation.name) if move.recipient_installation else None
            ),
            move.recycling_type.gtin
        )
        return WasteHandlingNotification(
            move.name, 
            move.transport_type.gtin, 
            takeover_loc, 
            handover_loc,
            move.abfallart.gtin, 
            move.quantification_type.gtin, 
            move.amount,
            movement_start_date=move.date.date() if move.date else None
        )

    def map_storage_state(self, state):
        return StorageState(
            installation_id=state.installation_id.gtin,
            reporting_date=state.reporting_date,
            stored_material=StoredMaterial(
                classification_code=state.abfallart.gtin if state.abfallart else None,
                quantification_type=state.quantification_type.gtin,
                weight=state.amount
            ),
            buffer_type_code=state.buffer_type_code
        )

    def map_storage_correction(self, correction):
        added = None
        if correction.amount > 0:
            added = CorrectionMaterial(correction.abfallart.gtin, correction.quantification_type.gtin, correction.amount)
        removed = None
        if correction.amount < 0:
            removed = CorrectionMaterial(correction.abfallart.gtin, correction.quantification_type.gtin, abs(correction.amount))
        return StorageCorrection(
            installation_id=correction.installation_id.gtin,
            reporting_date=correction.reporting_date,
            added_material=added,
            removed_material=removed
        )

    def map_reclassification(self, reclass):
        return ParserWasteReclassification(
            installation_id=reclass.installation_id.gtin,
            preliminary_classification_code=reclass.preliminary_abfallart.gtin,
            classification_code=reclass.new_abfallart.gtin,
            quantification_type=reclass.quantification_type.gtin,
            weight=reclass.amount,
            reclassification_reason_type_code=reclass.reclassification_reason_id.gtin,
            reporting_date=reclass.reporting_date
        )

    def map_remaining_capacity(self, cap):
        return RemainingCapacity(
            installation_id=cap.installation_id.gtin,
            reporting_date=cap.reporting_date,
            approved_remaining_capacity=cap.approved_remaining_capacity,
            physical_remaining_capacity=cap.physical_remaining_capacity
        )