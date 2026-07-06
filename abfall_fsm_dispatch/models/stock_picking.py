from odoo import fields, models


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
