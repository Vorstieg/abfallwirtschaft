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

    def _get_newest_valid_purchase_requisition(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        Requisition = self.env['purchase.requisition']
        domain = [
            ('vendor_id', '=', self.partner_id.id),
            ('state', '=', 'confirmed'),
            ('requisition_type', '=', 'blanket_order'),
            ('company_id', '=', self.company_id.id),
            '|', ('date_end', '=', False), ('date_end', '>=', today),
        ]
        requisition = Requisition.search(
            domain + [('date_start', '<=', today)],
            order='date_start desc, id desc',
            limit=1,
        )
        return requisition or Requisition.search(
            domain + [('date_start', '=', False)],
            order='id desc',
            limit=1,
        )

    @api.model_create_multi
    def create(self, vals_list):
        sales_orders = super().create(vals_list)
        for sales_order in sales_orders:
            purchase_order_vals = {
                'partner_id': sales_order.partner_id.id,
                'company_id': sales_order.company_id.id,
            }
            requisition = sales_order._get_newest_valid_purchase_requisition()
            if requisition:
                purchase_order_vals['requisition_id'] = requisition.id
            sales_order.purchase_order_id = self.env['purchase.order'].create(purchase_order_vals)
        return sales_orders
