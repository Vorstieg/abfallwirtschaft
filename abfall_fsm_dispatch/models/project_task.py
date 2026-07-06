from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round


class ProjectTask(models.Model):
    _inherit = 'project.task'

    dispatch_list_id = fields.Many2one(
        'abfall.dispatch.list',
        string='Dispatch List',
        index=True,
        copy=False,
        ondelete='set null',
    )
    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Transfer',
        index=True,
        copy=False,
        ondelete='set null',
    )

    _project_task_stock_picking_unique = models.Constraint(
        'unique(stock_picking_id)',
        'A stock transfer can only be linked to one field service task.',
    )

    def action_fsm_validate(self, stop_running_timers=False):
        if not stop_running_timers and self._has_running_fsm_timers():
            return super().action_fsm_validate(stop_running_timers)

        self._validate_dispatch_stock_pickings()
        return super().action_fsm_validate(stop_running_timers)

    def _has_running_fsm_timers(self):
        return bool(self.env['timer.timer'].search_count([
            ('parent_res_model', '=', 'project.task'),
            ('parent_res_id', 'in', self.ids),
        ], limit=1))

    def _validate_dispatch_stock_pickings(self):
        tasks = self.filtered(
            lambda task: task.dispatch_list_id
            and task.stock_picking_id
            and task.stock_picking_id.state not in ('done', 'cancel')
        )
        for task in tasks:
            picking = task.stock_picking_id
            task._set_dispatch_picking_done_quantities(picking)
            result = picking.with_context(
                skip_sms=True,
                skip_backorder=True,
                picking_ids_not_to_backorder=picking.ids,
            ).button_validate()
            if result is not True and picking.state != 'done':
                raise UserError(_(
                    'The stock transfer %(picking)s could not be validated automatically. '
                    'Open the transfer and validate it manually.',
                    picking=picking.display_name,
                ))

    def _set_dispatch_picking_done_quantities(self, picking):
        for move in picking.move_ids:
            if move.state in ('done', 'cancel'):
                continue
            rounding = move.product_uom.rounding
            if float_compare(move.quantity, move.product_uom_qty, precision_rounding=rounding) < 0:
                qty_to_do = float_round(
                    move.product_uom_qty - move.quantity,
                    precision_rounding=rounding,
                    rounding_method='HALF-UP',
                )
                move.quantity = qty_to_do
