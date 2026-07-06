from datetime import timedelta

from odoo import api, fields, models
from odoo.fields import Command


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    fsm_task_ids = fields.One2many(
        'project.task',
        'stock_picking_batch_id',
        string='Field Service Tasks',
        readonly=True,
    )
    fsm_task_count = fields.Integer(
        string='Field Service Tasks',
        compute='_compute_fsm_task_count',
    )

    @api.depends('fsm_task_ids')
    def _compute_fsm_task_count(self):
        for batch in self:
            batch.fsm_task_count = len(batch.fsm_task_ids)

    @api.model_create_multi
    def create(self, vals_list):
        batches = super().create(vals_list)
        batches._sync_fsm_tasks_from_pickings()
        return batches

    def write(self, vals):
        res = super().write(vals)
        self._sync_fsm_tasks_from_pickings()
        return res

    def action_view_fsm_tasks(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('project.action_view_task')
        action['domain'] = [('stock_picking_batch_id', '=', self.id)]
        action['context'] = {
            'default_stock_picking_batch_id': self.id,
            'fsm_mode': True,
        }
        return action

    def _sync_fsm_tasks_from_pickings(self):
        Task = self.env['project.task']
        for batch in self:
            fsm_project = batch._get_fsm_project()
            if not fsm_project:
                continue

            existing_tasks_by_picking = {
                task.stock_picking_id.id: task
                for task in Task.search([('stock_picking_batch_id', '=', batch.id)])
                if task.stock_picking_id
            }

            tasks_to_create = []
            for picking in batch.picking_ids:
                if picking.id in existing_tasks_by_picking:
                    task = existing_tasks_by_picking[picking.id]
                    task.write(batch._prepare_fsm_task_vals(picking, fsm_project))
                    continue
                tasks_to_create.append(batch._prepare_fsm_task_vals(picking, fsm_project))

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
        scheduled_start = self.scheduled_date or picking.scheduled_date
        scheduled_end = scheduled_start + timedelta(hours=1) if scheduled_start else False
        description_parts = [
            f'Batch: {self.name}',
            f'Transfer: {picking.name}',
        ]
        if picking.origin:
            description_parts.append(f'Origin: {picking.origin}')
        if self.description:
            description_parts.append(f'Batch Description: {self.description}')

        vals = {
            'name': f'{self.name} - {picking.name}',
            'project_id': fsm_project.id,
            'partner_id': picking.partner_id.id,
            'company_id': self.company_id.id,
            'planned_date_begin': scheduled_start,
            'date_deadline': scheduled_end,
            'description': '\n'.join(description_parts),
            'stock_picking_batch_id': self.id,
            'stock_picking_id': picking.id,
        }

        if self.user_id:
            vals['user_ids'] = [Command.set([self.user_id.id])]

        if 'driver_id' in self._fields and self.driver_id and self.driver_id.user_ids:
            driver_user = self.driver_id.user_ids[0]
            vals['user_ids'] = [Command.set([driver_user.id])]

        return vals
