from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command


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
        return self.env['project.project'].search([
            ('is_fsm', '=', True),
            ('company_id', '=', self.company_id.id),
        ], order='sequence, id', limit=1)

    def _prepare_fsm_task_vals(self, picking, fsm_project):
        self.ensure_one()
        scheduled_start = picking.scheduled_date
        scheduled_end = scheduled_start + timedelta(hours=1) if scheduled_start else False
        description_parts = [
            _('Dispatch List: %(dispatch)s', dispatch=self.name),
            _('Transfer: %(transfer)s', transfer=picking.name),
            _('Operation Type: %(operation_type)s', operation_type=picking.picking_type_id.display_name),
        ]
        if picking.origin:
            description_parts.append(_('Origin: %(origin)s', origin=picking.origin))
        if self.description:
            description_parts.append(_('Dispatch Description: %(description)s', description=self.description))

        vals = {
            'name': f'{self.name} - {picking.name}',
            'project_id': fsm_project.id,
            'partner_id': picking.partner_id.id,
            'company_id': self.company_id.id,
            'planned_date_begin': scheduled_start,
            'date_deadline': scheduled_end,
            'description': '\n'.join(description_parts),
            'dispatch_list_id': self.id,
            'stock_picking_id': picking.id,
        }

        if self.user_id:
            vals['user_ids'] = [Command.set([self.user_id.id])]

        return vals
