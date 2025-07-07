from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    purchase_order_id = fields.Many2one('purchase.order', string="Related Purchase Order")

    purchase_order_line_ids = fields.One2many(
        related='purchase_order_id.order_line',
        string="Purchase Order Lines",
        readonly=True,
    )

    purchase_order_tax_totals = fields.Binary(
        compute='_compute_po_tax_totals',
        string="Purchase Order Tax totals",
        readonly=True,
    )

    def _compute_po_tax_totals(self):
        """
        Computes the total tax amount from the linked purchase order.
        """
        for order in self:
            if order.purchase_order_id:
                order.purchase_order_tax_totals = order.purchase_order_id.tax_totals
            else:
                order.purchase_order_tax_totals = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        sales_order = super().create(vals_list)
        sales_order.purchase_order_id = self.env['purchase.order'].create({
            'partner_id': sales_order.partner_id.id,
        })
        return sales_order