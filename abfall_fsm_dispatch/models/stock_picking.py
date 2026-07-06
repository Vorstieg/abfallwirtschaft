from odoo import api, fields, models
from odoo.tools.float_utils import float_round


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    dispatch_list_ids = fields.Many2many(
        'abfall.dispatch.list',
        'abfall_dispatch_list_stock_picking_rel',
        'picking_id',
        'dispatch_list_id',
        string='Dispatch Lists',
        copy=False,
    )
    dispatch_list_count = fields.Integer(
        string='Dispatch List Count',
        compute='_compute_dispatch_list_count',
    )

    def _compute_dispatch_list_count(self):
        for picking in self:
            picking.dispatch_list_count = len(picking.dispatch_list_ids)

    def action_view_dispatch_lists(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('abfall_fsm_dispatch.action_abfall_dispatch_list')
        action['domain'] = [('id', 'in', self.dispatch_list_ids.ids)]
        action['context'] = {
            'default_company_id': self.company_id.id,
            'default_picking_ids': [(4, self.id)],
        }
        return action


class StockMove(models.Model):
    _inherit = 'stock.move'

    show_weigh_quantity_button = fields.Boolean(
        string='Show Weigh Quantity Button',
        compute='_compute_show_weigh_quantity_button',
    )

    @api.depends('product_uom', 'state')
    def _compute_show_weigh_quantity_button(self):
        for move in self:
            move.show_weigh_quantity_button = (
                move.state not in ('done', 'cancel')
                and move._is_abfall_weight_uom()
            )

    def action_weigh_quantity(self):
        for move in self:
            if move.state in ('done', 'cancel') or not move._is_abfall_weight_uom():
                continue
            move.quantity = float_round(
                move.product_uom_qty * 0.9,
                precision_rounding=move.product_uom.rounding,
                rounding_method='HALF-UP',
            )

    def _is_abfall_weight_uom(self):
        self.ensure_one()
        uom_kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
        return bool(uom_kg and self.product_uom and self.product_uom._has_common_reference(uom_kg))
