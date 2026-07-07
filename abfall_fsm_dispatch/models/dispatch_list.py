from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import formatLang, html_escape


class AbfallDispatchList(models.Model):
    _name = 'abfall.dispatch.list'
    _description = 'Dispatch List'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc, id desc'

    name = fields.Char(
        string='Dispatch List',
        default='New',
        required=True,
        copy=False,
        readonly=True,
    )
    description = fields.Char()
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        tracking=True,
        check_company=True,
    )
    scheduled_date = fields.Datetime(
        string='Scheduled Date',
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        tracking=True,
    )
    hazardous_waste_type_ids = fields.Many2many(
        'waste.type',
        string='Hazardous Waste Types',
        compute='_compute_vehicle_waste_warning',
    )
    vehicle_missing_waste_type_ids = fields.Many2many(
        'waste.type',
        string='Missing Vehicle Waste Type Approvals',
        compute='_compute_vehicle_waste_warning',
    )
    vehicle_waste_warning = fields.Char(
        string='Vehicle Waste Warning',
        compute='_compute_vehicle_waste_warning',
    )
    vehicle_waste_management_enabled = fields.Boolean(
        string='Vehicle Waste Management Enabled',
        compute='_compute_vehicle_waste_management_enabled',
    )
    vehicle_category_id = fields.Many2one(
        'fleet.vehicle.model.category',
        string='Vehicle Category',
        compute='_compute_vehicle_category_id',
        store=True,
        readonly=False,
        tracking=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        default='draft',
        required=True,
        tracking=True,
        copy=False,
        index=True,
    )
    picking_ids = fields.Many2many(
        'stock.picking',
        'abfall_dispatch_list_stock_picking_rel',
        'dispatch_list_id',
        'picking_id',
        string='Transfers',
        domain="[('company_id', '=', company_id), ('state', 'not in', ('done', 'cancel'))]",
        check_company=True,
    )
    picking_count = fields.Integer(
        string='Transfer Count',
        compute='_compute_counts',
    )
    fsm_task_ids = fields.One2many(
        'project.task',
        'dispatch_list_id',
        string='Field Service Tasks',
        readonly=True,
    )
    fsm_task_count = fields.Integer(
        string='Field Service Task Count',
        compute='_compute_counts',
    )

    @api.depends('picking_ids', 'fsm_task_ids')
    def _compute_counts(self):
        for dispatch in self:
            dispatch.picking_count = len(dispatch.picking_ids)
            dispatch.fsm_task_count = len(dispatch.fsm_task_ids)

    @api.depends('vehicle_id')
    def _compute_vehicle_category_id(self):
        for dispatch in self:
            dispatch.vehicle_category_id = dispatch.vehicle_id.category_id

    @api.model
    def _is_vehicle_waste_management_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'abfall_fsm_dispatch.vehicle_waste_management'
        )
        return value in ('1', 'True', 'true')

    def _compute_vehicle_waste_management_enabled(self):
        enabled = self._is_vehicle_waste_management_enabled()
        for dispatch in self:
            dispatch.vehicle_waste_management_enabled = enabled

    @api.depends(
        'vehicle_id',
        'vehicle_id.model_id.allowed_waste_type_ids',
        'picking_ids.move_ids.product_id.waste_type_id',
        'picking_ids.move_ids.product_id.waste_type_id.dangerous',
        'picking_ids.move_line_ids.product_id.waste_type_id',
        'picking_ids.move_line_ids.product_id.waste_type_id.dangerous',
    )
    def _compute_vehicle_waste_warning(self):
        enabled = self._is_vehicle_waste_management_enabled()
        for dispatch in self:
            hazardous_waste_types = dispatch._get_hazardous_waste_types()
            allowed_waste_types = dispatch.vehicle_id.model_id.allowed_waste_type_ids
            missing_waste_types = hazardous_waste_types - allowed_waste_types if enabled and dispatch.vehicle_id else self.env['waste.type']

            dispatch.hazardous_waste_type_ids = hazardous_waste_types
            dispatch.vehicle_missing_waste_type_ids = missing_waste_types
            dispatch.vehicle_waste_warning = dispatch._prepare_vehicle_waste_warning(missing_waste_types) if missing_waste_types else False

    def _get_hazardous_waste_types(self):
        self.ensure_one()
        products = self.picking_ids.move_ids.product_id | self.picking_ids.move_line_ids.product_id
        return products.mapped('waste_type_id').filtered('dangerous')

    def _prepare_vehicle_waste_warning(self, missing_waste_types):
        self.ensure_one()
        waste_types = ', '.join(missing_waste_types.mapped('display_name'))
        vehicle = self.vehicle_id.display_name
        return _(
            'Warnung: %(vehicle)s ist für diese gefährlichen Abfallarten nicht freigegeben: %(waste_types)s',
            vehicle=vehicle,
            waste_types=waste_types,
        )

    @api.onchange('vehicle_id', 'picking_ids')
    def _onchange_vehicle_waste_warning(self):
        if not self.vehicle_waste_warning:
            return
        return {
            'warning': {
                'title': _('Abfallarten-Freigabe am Fahrzeug fehlt'),
                'message': _(
                    '%(vehicle)s ist für diese gefährlichen Abfallarten nicht freigegeben: %(waste_types)s',
                    vehicle=self.vehicle_id.display_name,
                    waste_types=', '.join(self.vehicle_missing_waste_type_ids.mapped('display_name')),
                ),
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('abfall.dispatch.list') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if {'picking_ids', 'user_id', 'scheduled_date', 'description'} & set(vals):
            self.filtered(lambda dispatch: dispatch.state != 'draft')._sync_fsm_tasks_from_pickings()
        return res

    @api.constrains('company_id', 'picking_ids', 'state')
    def _check_picking_ids(self):
        for dispatch in self:
            invalid_state_pickings = dispatch.picking_ids.filtered(lambda picking: picking.state in ('done', 'cancel'))
            if invalid_state_pickings:
                raise ValidationError(_(
                    'Done or cancelled transfers cannot be added to a dispatch list: %(pickings)s',
                    pickings=', '.join(invalid_state_pickings.mapped('name')),
                ))

            wrong_company_pickings = dispatch.picking_ids.filtered(lambda picking: picking.company_id != dispatch.company_id)
            if wrong_company_pickings:
                raise ValidationError(_(
                    'Transfers from another company cannot be added to this dispatch list: %(pickings)s',
                    pickings=', '.join(wrong_company_pickings.mapped('name')),
                ))

            if dispatch.state in ('done', 'cancel') or not dispatch.picking_ids:
                continue

            other_dispatch = self.search([
                ('id', '!=', dispatch.id),
                ('state', 'not in', ('done', 'cancel')),
                ('picking_ids', 'in', dispatch.picking_ids.ids),
            ], limit=1)
            if other_dispatch:
                duplicate_pickings = dispatch.picking_ids & other_dispatch.picking_ids
                raise ValidationError(_(
                    'Transfers can only be on one active dispatch list. %(pickings)s are already on %(dispatch)s.',
                    pickings=', '.join(duplicate_pickings.mapped('name')),
                    dispatch=other_dispatch.display_name,
                ))

    def action_confirm(self):
        for dispatch in self:
            if not dispatch.picking_ids:
                raise UserError(_('Add at least one transfer before confirming the dispatch list.'))
        self.write({'state': 'confirmed'})
        self._sync_fsm_tasks_from_pickings()
        return True

    def action_start(self):
        self.write({'state': 'in_progress'})
        self._sync_fsm_tasks_from_pickings()
        return True

    def action_done(self):
        self.write({'state': 'done'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
        return True

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('stock.action_picking_tree_all')
        action['domain'] = [('id', 'in', self.picking_ids.ids)]
        action['context'] = {'default_company_id': self.company_id.id}
        return action

    def action_view_fsm_tasks(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('project.action_view_task')
        action['domain'] = [('dispatch_list_id', '=', self.id)]
        action['context'] = {
            'default_dispatch_list_id': self.id,
            'fsm_mode': True,
        }
        return action

    def _sync_fsm_tasks_from_pickings(self):
        Task = self.env['project.task']
        for dispatch in self:
            fsm_project = dispatch._get_fsm_project()
            if not fsm_project:
                continue

            tasks_by_picking = {
                task.stock_picking_id.id: task
                for task in Task.search([('stock_picking_id', 'in', dispatch.picking_ids.ids)])
                if task.stock_picking_id
            }

            tasks_to_create = []
            for picking in dispatch.picking_ids:
                vals = dispatch._prepare_fsm_task_vals(picking, fsm_project)
                task = tasks_by_picking.get(picking.id)
                if task:
                    task.write(vals)
                    continue
                tasks_to_create.append(vals)

            if tasks_to_create:
                Task.create(tasks_to_create)

    def _get_fsm_project(self):
        self.ensure_one()
        fsm_project = self.env['project.project'].search([
            ('is_fsm', '=', True),
            ('company_id', '=', self.company_id.id),
        ], order='sequence, id', limit=1)
        if fsm_project:
            self._ensure_fsm_project_worksheet(fsm_project)
        return fsm_project

    def _ensure_fsm_project_worksheet(self, fsm_project):
        vals = {}
        if 'allow_worksheets' in fsm_project._fields and not fsm_project.allow_worksheets:
            vals['allow_worksheets'] = True
        if 'worksheet_template_id' in fsm_project._fields and not fsm_project.worksheet_template_id:
            worksheet_template = self._get_abfall_dispatch_worksheet_template()
            if worksheet_template:
                vals['worksheet_template_id'] = worksheet_template.id
        if vals:
            fsm_project.write(vals)

    def _get_abfall_dispatch_worksheet_template(self):
        return self.env.ref('abfall_fsm_dispatch.abfall_dispatch_worksheet_template', raise_if_not_found=False)

    def _prepare_fsm_task_vals(self, picking, fsm_project):
        self.ensure_one()
        scheduled_start = picking.scheduled_date
        scheduled_end = scheduled_start + timedelta(hours=1) if scheduled_start else False
        description_parts = [
            _('Dispositionsliste: %(dispatch)s', dispatch=self.name),
            _('Transfer: %(transfer)s', transfer=picking.name),
            _('Vorgangsart: %(operation_type)s', operation_type=picking.picking_type_id.display_name),
        ]
        if picking.origin:
            description_parts.append(_('Herkunft: %(origin)s', origin=picking.origin))
        if picking.partner_id:
            description_parts.append(_('Kunde: %(customer)s', customer=picking.partner_id.display_name))
            contact_address = picking.partner_id.contact_address
            if contact_address:
                description_parts.append(_('Adresse: %(address)s', address=contact_address))
        if self.vehicle_id:
            description_parts.append(_('Fahrzeug: %(vehicle)s', vehicle=self.vehicle_id.display_name))
        elif self.vehicle_category_id:
            description_parts.append(_('Fahrzeugkategorie: %(vehicle_category)s', vehicle_category=self.vehicle_category_id.display_name))
        if self.description:
            description_parts.append(_('Dispo-Hinweis: %(description)s', description=self.description))
        instruction = self._prepare_fsm_task_instruction(picking)
        if instruction:
            description_parts.extend(['', instruction])

        vals = {
            'name': f'{self.name} - {picking.name}',
            'project_id': fsm_project.id,
            'partner_id': picking.partner_id.id,
            'company_id': self.company_id.id,
            'planned_date_begin': scheduled_start,
            'date_deadline': scheduled_end,
            'description': self._format_fsm_task_description(description_parts),
            'dispatch_list_id': self.id,
            'stock_picking_id': picking.id,
        }

        if self.user_id:
            vals['user_ids'] = [Command.set([self.user_id.id])]

        if 'worksheet_template_id' in self.env['project.task']._fields:
            worksheet_template = self._get_abfall_dispatch_worksheet_template() or fsm_project.worksheet_template_id
            if worksheet_template:
                vals['worksheet_template_id'] = worksheet_template.id

        return vals

    def _format_fsm_task_description(self, description_parts):
        escaped_parts = [
            str(html_escape(part)).replace('\n', '<br/>')
            for part in description_parts
        ]
        return '<br/>'.join(escaped_parts)

    def _prepare_fsm_task_instruction(self, picking):
        self.ensure_one()
        sections = self._get_fsm_picking_instruction_sections(picking)
        if not any(sections.values()):
            return False

        lines = [_('Arbeitsanweisungen')]
        section_labels = {
            'pickup': _('Abholung'),
            'delivery': _('Lieferung'),
            'internal': _('Interne Bewegung'),
            'unknown': _('Nicht klassifiziert'),
        }
        for section_key in ('pickup', 'delivery', 'internal', 'unknown'):
            section_lines = sections[section_key]
            if not section_lines:
                continue
            lines.extend(['', '%s:' % section_labels[section_key]])
            lines.extend(section_lines)
        return '\n'.join(lines)

    def _get_fsm_picking_instruction_sections(self, picking):
        sections = {
            'pickup': [],
            'delivery': [],
            'internal': [],
            'unknown': [],
        }
        for move in picking.move_ids.filtered(lambda stock_move: stock_move.state != 'cancel'):
            move_lines = move.move_line_ids.filtered(lambda line: line.state != 'cancel')
            if move_lines:
                for move_line in move_lines:
                    operation = self._classify_fsm_move_operation(move, move_line)
                    sections[operation].extend(self._format_fsm_instruction_line(move, move_line))
                continue
            operation = self._classify_fsm_move_operation(move)
            sections[operation].extend(self._format_fsm_instruction_line(move))
        return sections

    def _classify_fsm_move_operation(self, move, move_line=False):
        source_location = move_line.location_id if move_line and move_line.location_id else move.location_id
        destination_location = move_line.location_dest_id if move_line and move_line.location_dest_id else move.location_dest_id

        if source_location.usage == 'customer' or move.picking_type_id.code == 'incoming':
            return 'pickup'
        if destination_location.usage == 'customer' or move.picking_type_id.code == 'outgoing':
            return 'delivery'
        if source_location.usage == 'internal' and destination_location.usage == 'internal':
            return 'internal'
        return 'unknown'

    def _format_fsm_instruction_line(self, move, move_line=False):
        product = move_line.product_id if move_line and move_line.product_id else move.product_id
        product_uom = move_line.product_uom_id if move_line and move_line.product_uom_id else move.product_uom
        quantity = self._get_fsm_instruction_quantity(move, move_line)
        source_location = move_line.location_id if move_line and move_line.location_id else move.location_id
        destination_location = move_line.location_dest_id if move_line and move_line.location_dest_id else move.location_dest_id
        lot = move_line.lot_id if move_line and move_line.lot_id else self._get_fsm_instruction_move_lot(move)

        lines = ['- %s: %s' % (_('Produkt'), product.display_name)]
        if lot:
            lines.append('  %s: %s' % (_('Container-Seriennummer'), lot.name))
        lines.append('  %s: %s %s' % (
            _('Menge'),
            formatLang(self.env, quantity),
            product_uom.display_name,
        ))
        if source_location:
            lines.append('  %s: %s' % (_('Von'), source_location.display_name))
        if destination_location:
            lines.append('  %s: %s' % (_('Nach'), destination_location.display_name))
        return lines

    def _get_fsm_instruction_quantity(self, move, move_line=False):
        if move_line:
            if 'quantity' in move_line._fields:
                return move_line.quantity or move.product_uom_qty
            if 'qty_done' in move_line._fields:
                return move_line.qty_done or move.product_uom_qty
        if 'quantity' in move._fields and move.quantity:
            return move.quantity
        return move.product_uom_qty

    def _get_fsm_instruction_move_lot(self, move):
        if 'lot_ids' in move._fields and move.lot_ids:
            return move.lot_ids[:1]
        return self.env['stock.lot']
