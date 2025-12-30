import logging
import os
import uuid

from odoo import models, fields, _, api
from odoo.exceptions import UserError

from .library.auth import Auth
from .library.mappings import *
from .library.message.begleitschein_message_service import VebsvBegleitschein
from .library.vebsv_begleitschein import VebsvBegleitscheinLine, MessageRequestType, TransferRequestType
from .library.vebsv_service import VEBSVService

_logger = logging.getLogger(__name__)

COMPANY_GLN_MISSING = "You need to have a GLN configured for your company"


class WasteBegleitscheinStage(models.Model):
    _name = 'waste.begleitschein.stage'
    _description = 'Begleitschein Stage'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(string='Folded in Kanban')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('declared', 'Declared'),
        ('confirmed', 'Confirmed'),
        ('in_transport', 'In Transport'),
        ('transport_complete', 'Transport complete'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='Related Status', required=True)


class Begleitschein(models.Model, VebsvBegleitschein):
    _name = "waste.begleitschein"
    _description = "Waste Transport Accompanying Document"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    stock_picking_id = fields.Many2one(
        'stock.picking', 'Stock Picking', index=True, ondelete='set null',
        help="Related stock picking/delivery order")

    name = fields.Char(string='Begleitschein Ref', required=True, copy=False,
        help="Unique reference number for this Begleitschein")

    source_partner_id = fields.Many2one('res.partner', string='Source Partner', required=True, change_default=True,
                                        tracking=True, help="Partner responsible for waste handover")
    target_partner_id = fields.Many2one('res.partner', string='Target Partner', required=True, change_default=True,
                                        tracking=True, help="Partner responsible for waste takeover")
    organizing_partner_id = fields.Many2one('res.partner', string='Organizing Partner',
                                            help="Partner organizing the waste transport")
    # When implementing drop-shipping with multiple partners, this needs to change to a many2many
    dropship_partner_id = fields.Many2one('res.partner', string='Dropship Partner',
                                          help="Intermediate partner in dropship scenarios")
    company_partner_id = fields.Many2one('res.partner', string="Company Partner", related='company_id.partner_id',
                                         store=True, readonly=True)
    transport_partner_id = fields.Many2one('res.partner', string="Transport Partner",
                                           help="Carrier responsible for the physical transport")
    transport_mode_id = fields.Many2one('waste.transport.mode', string="Transport Mode")
    transport_mode_gtin = fields.Char(related='transport_mode_id.gtin')
    quantification_type_id = fields.Many2one('waste.quantification.type', string="Quantification Type")
    source_installation = fields.Many2one('waste.treatment.installation', string='Source Installation',
                                          help="Treatment installation where waste originates")
    source_site = fields.Many2one('waste.treatment.site', string='Source Site',
                                  help="Treatment site where waste originates")

    target_installation = fields.Many2one('waste.treatment.installation', string='Target Installation',
                                          help="Target treatment installation for waste delivery")
    target_site = fields.Many2one('waste.treatment.site', string='Target Site',
                                  help="Target treatment site for waste delivery")

    begleitschein_lines = fields.One2many(
        comodel_name='waste.begleitschein.line',
        inverse_name='begleitschein_id',
        string="Begleitschein Lines",
        copy=True, auto_join=False)

    request_identifiers = fields.One2many(
        comodel_name='waste.begleitschein.request.identifier',
        inverse_name='begleitschein_id',
        string="Begleitschein Request Identifiers",
        copy=False, auto_join=False)

    shipment_uuid = fields.Char('Shipment UUID', default=lambda x: uuid.uuid4())
    business_case_uuid = fields.Char('Business Case UUID', default=lambda x: uuid.uuid4())
    transport_uuid = fields.Char('Transport UUID', default=lambda x: uuid.uuid4())

    state = fields.Selection([
        ('draft', 'Draft'),
        ('declared', 'Declared'),
        ('confirmed', 'Confirmed'),
        ('in_transport', 'In Transport'),
        ('transport_complete', 'Transport complete'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', readonly=True)

    stage_id = fields.Many2one('waste.begleitschein.stage', string='Stage',
                               compute='_compute_stage_id', store=True, group_expand='_read_group_stage_ids')


    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)

    total_product_qty = fields.Float(
        string='Total Product Quantity',
        compute='_compute_total_product_qty',
        store=True,
    )
    self_is_main_organizer = fields.Boolean(string="Self is Main Organizer", compute='_compute_self_is_main_organizer',
                                            store=True)

    is_cancel_button_visible = fields.Boolean(string="Cancel Button is visible",
                                              compute='_compute_is_cancel_button_visible',
                                              store=True)
    contains_pop = fields.Boolean(string='Contains POP', compute='_compute_contains_pop', store=True)

    @api.depends('state')
    def _compute_stage_id(self):
        for record in self:
            if record.state:
                record.stage_id = self.env['waste.begleitschein.stage'].search([('state', '=', record.state)], limit=1)
            else:
                record.stage_id = False

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return self.env['waste.begleitschein.stage'].search([])


    @api.onchange('source_site')
    def _onchange_source_site(self):
        self.source_installation = False

    @api.onchange('target_site')
    def _onchange_target_site(self):
        self.target_installation = False

    @api.depends('begleitschein_lines.product_qty')
    def _compute_total_product_qty(self):
        for record in self:
            record.total_product_qty = sum(record.begleitschein_lines.mapped('product_qty'))

    @api.depends('begleitschein_lines.contains_pop')
    def _compute_contains_pop(self):
        for record in self:
            record.contains_pop = any(record.begleitschein_lines.mapped('contains_pop'))

    @api.depends('organizing_partner_id', 'company_partner_id')
    def _compute_self_is_main_organizer(self):
        for record in self:
            record.self_is_main_organizer = record.organizing_partner_id == record.company_partner_id

    @api.depends('organizing_partner_id', 'company_partner_id', 'state')
    def _compute_is_cancel_button_visible(self):
        for record in self:
            match record.state:
                case "draft":
                    record.is_cancel_button_visible = False
                case "declared":
                    record.is_cancel_button_visible = record.organizing_partner_id == record.company_partner_id
                case "confirmed":
                    record.is_cancel_button_visible = record.company_partner_id.is_source(record)
                case "in_transport":
                    record.is_cancel_button_visible = (record.organizing_partner_id == record.company_partner_id
                                                       or record.company_partner_id.is_carrier(record))
                case "transport_complete":
                    record.is_cancel_button_visible = (record.organizing_partner_id == record.company_partner_id
                                                       or record.company_partner_id.is_carrier(record))
                case "done":
                    record.is_cancel_button_visible = (record.company_partner_id.is_target(record)
                                                       or record.company_partner_id.is_carrier(record))
                case "canceled":
                    record.is_cancel_button_visible = record.organizing_partner_id == record.company_partner_id


    @api.model_create_multi
    def create(self, vals_list):
        for value in vals_list:
            if not value.get("company_id"):
                value["company_id"] = self.env.user.company_id.id
            if not value.get("organizing_partner_id"):
                value["organizing_partner_id"] = self.env.user.company_id.partner_id.id
            if not value.get("transport_partner_id"):
                value["transport_partner_id"] = self.env.user.company_id.partner_id.id
            if not value.get("transport_mode_id"):
                # Default to Road (Strasse)
                road = self.env['waste.transport.mode'].search([('gtin', '=', '9008390100059')], limit=1)
                if road:
                    value["transport_mode_id"] = road.id

        return super().create(vals_list)

    def action_view_stock_picking(self):
        """Smart button action to view the related stock picking."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Picking'),
            'res_model': 'stock.picking',
            'res_id': self.stock_picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def start_begleitschein(self):
        source_partner_gln = self.source_partner_id.get_person_gln()
        target_partner_gln = self.target_partner_id.get_person_gln()

        sms_telephone_number = self.source_partner_id.sms_solution_phone_number if self.source_partner_id.enable_sms_solution else False

        if source_partner_gln == target_partner_gln:
            raise UserError(_("Handover and takeover party cannot be the same."))

        if len(self.begleitschein_lines) == 0:
            raise UserError(_("You need at least one product with a waste code"))
        if self.target_partner_id.enable_sms_solution and not sms_telephone_number:
            raise UserError(_("If the sms solution is active, the partner needs to have a phone number configured"))

        has_dangerous_waste = self._get_unified_service().start_begleitschein(self, self.company_partner_id,
                                                                              sms_telephone_number)

        if not has_dangerous_waste:
            self.state = 'confirmed'
        else:
            self.state = 'declared'

    def confirm_begleitschein(self):
        if not self.source_site.gtin:
            raise UserError(_("You need to define a source site."))
        self._get_unified_service().confirm_begleitschein(self)

        self.state = 'confirmed'

    def start_transport(self):
        if self.state != 'confirmed':
            raise UserError(_("You can only start transport for a confirmed begleitschein."))
        if not self.target_site.gtin:
            raise UserError(_("You need to define a target site."))
        if not self.source_site.gtin:
            raise UserError(_("You need to define a source site."))

        self._get_unified_service().start_transport(self, self.company_partner_id, self.name)
        self.state = 'in_transport'

    def end_transport(self):
        if self.state != 'in_transport' and self.state != 'transport_complete':
            raise UserError(_("Can not finish a begleitschein, that is still in transport"))

        self._get_unified_service().end_transport(self, self.company_partner_id)

        self.state = 'done'

    def cancel_begleitschein(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cancel Begleitschein'),
            'res_model': 'begleitschein.cancel.wizard',
            'target': 'new',
            'view_mode': 'form',
            'context': {
                'default_begleitschein_id': self.id,
                'default_cancel_state': self.state,
            },
        }

    def action_cancel(self, revocation_reason):
        self.ensure_one()
        service = self._get_unified_service()

        if self.state == 'declared':
            service.cancel_declared(self, self.company_partner_id, revocation_reason)
            self.write({
                'state': 'draft',
                'shipment_uuid': str(uuid.uuid4()),
                'business_case_uuid': str(uuid.uuid4()),
                'transport_uuid': str(uuid.uuid4()),
            })
        elif self.state == 'confirmed':
            service.cancel_confirmed(self, revocation_reason)
            self.state = 'declared'
        elif self.state == 'in_transport':
            service.cancel_in_transport(self, self.company_partner_id, revocation_reason)
            self.write({
                'state': 'confirmed',
                'transport_uuid': str(uuid.uuid4())
            })
        elif self.state == 'done':
            service.cancel_done(self, self.company_partner_id, revocation_reason)
            self.state = 'in_transport'

    def _get_unified_service(self):
        config_params = self.env['ir.config_parameter'].sudo()

        edm_username = config_params.get_param('waste_management.edm_username')
        edm_secret = config_params.get_param('waste_management.edm_secret')

        connector_id = os.getenv('CONNECTOR_ID')
        connector_key = os.getenv('CONNECTOR_KEY')

        if not edm_username or not edm_secret:
            raise UserError(_("You need to configure edm username and secret."))
        if not connector_id or not connector_key:
            raise UserError(_("You need to configure connector id and connector key."))

        auth = Auth(edm_username, edm_secret, connector_id, connector_key,
                    config_params.get_param('waste_management.edm_db_uuid'))
        return VEBSVService(auth)

    def get_shipment(self):
        shipment_items = [line.get_shipment_item(index + 1) for index, line in enumerate(self.begleitschein_lines)]
        return Shipment(self.shipment_uuid, self.name, shipment_items,
                        PlannedWaypoint(Period(datetime.now(), datetime.now()), "pickup_site", "handover"),
                        PlannedWaypoint(Period(datetime.now(), datetime.now()), "dropoff_site", "takeover"))

    def get_request_identifier(self, message_request_type: MessageRequestType, suffix: str = ""):
        return self.request_identifiers.filtered(lambda r: r.name == (message_request_type.name + suffix)).uuid

    def add_request_identifier(self, message_request_type: MessageRequestType, suffix: str, uuid: str):
        name = message_request_type.name + suffix
        existing = self.request_identifiers.filtered(lambda r: r.name == name)
        if existing:
            existing.write({'uuid': uuid})
        else:
            self.write({'request_identifiers': [(0, 0, {'name': name, 'uuid': uuid})]})


class BegleitscheinLine(models.Model, VebsvBegleitscheinLine):
    _name = "waste.begleitschein.line"
    _description = "Waste Transport Line Item"
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Product",
        change_default=True, ondelete='restrict', index='btree_not_null')

    abfallart = fields.Many2one('waste.type', "Abfallart")
    waste_contamination = fields.Many2one('waste.contamination.type', "Kontaminationsgruppe")
    product_qty = fields.Float(string="Quantity", default=1.0, required=True)
    contains_pop = fields.Boolean(string="POP", default=False)

    begleitschein_id = fields.Many2one(
        'waste.begleitschein', 'Begleitschein', index=True, ondelete='set null')

    vebsv_id = fields.Char(
        string="VEBSV ID", store=True, readonly=False, required=False)

    quantification_type_id = fields.Many2one('waste.quantification.type', string="Quantification Type")
    quantification_type_gtin = fields.Char(related='quantification_type_id.gtin')

    request_identifiers = fields.One2many(
        comodel_name='waste.line.request.identifier',
        inverse_name='line_id',
        string="Line Request Identifiers",
        copy=False, auto_join=False)

    def write_vebsv_id(self, vebsv_id: str):
        self.vebsv_id = vebsv_id

    def get_request_identifier(self, transfer_request_type: TransferRequestType):
        return self.request_identifiers.filtered(lambda r: r.name == transfer_request_type.name).uuid

    def add_request_identifier(self, transfer_request_type: TransferRequestType, uuid: str):
        name = transfer_request_type.name
        existing = self.request_identifiers.filtered(lambda r: r.name == name)
        if existing:
            existing.write({'uuid': uuid})
        else:
            self.write({'request_identifiers': [(0, 0, {'name': name, 'uuid': uuid})]})

    def get_shipment_item(self, line_item_number=0):
        return ShipmentItem(
            uuid.uuid4(),
            line_item_number,
            self.abfallart.gtin,
            self.waste_contamination.gtin,
            self.abfallart.note,
            self.vebsv_id,
            self.contains_pop,
            NetProperty("9008390104439", self.product_qty, self.quantification_type_gtin or "9008390100028")
        )

    def requires_reporting(self):
        return self.abfallart.dangerous or self.contains_pop


class BegleitscheinRequestIdentifier(models.Model):
    _name = 'waste.begleitschein.request.identifier'
    _description = 'Request Identifier'

    begleitschein_id = fields.Many2one(
        comodel_name='waste.begleitschein',
        string='Begleitschein',
        index=True,
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        string='Request Name',
        required=True,
        help="The name of request"
    )

    uuid = fields.Char(
        string='Request UUID',
        required=True,
        help="The uuid to identify the request"
    )


class LineRequestIdentifier(models.Model):
    _name = 'waste.line.request.identifier'
    _description = 'Request Identifier'

    line_id = fields.Many2one(
        comodel_name='waste.begleitschein.line',
        string='Begleitschein Line',
        index=True,
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        string='Request Name',
        required=True,
        help="The name of request"
    )

    uuid = fields.Char(
        string='Request UUID',
        required=True,
        help="The uuid to identify the request"
    )
