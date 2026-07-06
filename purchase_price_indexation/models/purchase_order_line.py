from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    index_price_date = fields.Date(string='Index Price Date', default=fields.Date.context_today)
    has_indexed_price = fields.Boolean(string='Indexed Price', compute='_compute_has_indexed_price')

    @api.depends(
        'product_id',
        'product_uom_id',
        'order_id.requisition_id',
        'order_id.requisition_id.line_ids.product_id',
        'order_id.requisition_id.line_ids.product_uom_id',
        'order_id.requisition_id.line_ids.is_indexed_price',
    )
    def _compute_has_indexed_price(self):
        for line in self:
            req_line = line._get_indexed_requisition_line()
            line.has_indexed_price = bool(req_line and req_line.is_indexed_price)

    def _get_indexed_requisition_line(self):
        self.ensure_one()
        requisition = self.order_id.requisition_id
        if not requisition or not self.product_id or self.display_type:
            return self.env['purchase.requisition.line']

        req_lines = requisition.line_ids.filtered(lambda l: l.product_id == self.product_id)
        if not req_lines:
            return self.env['purchase.requisition.line']

        req_line = req_lines.filtered(lambda l: l.product_uom_id == self.product_uom_id)[:1] or req_lines[:1]
        return req_line[:1]

    def _get_index_price_date(self):
        self.ensure_one()
        if self.index_price_date:
            return self.index_price_date
        if self.order_id.date_order:
            return fields.Datetime.to_datetime(self.order_id.date_order).date()
        return fields.Date.context_today(self)

    def _update_indexed_price_unit(self):
        for line in self:
            req_line = line._get_indexed_requisition_line()
            if not req_line or not req_line.is_indexed_price:
                continue
            price = req_line._get_indexed_price(line._get_index_price_date())
            line.price_unit = req_line.product_uom_id._compute_price(price, line.product_uom_id)

    def _compute_price_unit_and_date_planned_and_name(self):
        super()._compute_price_unit_and_date_planned_and_name()
        self._update_indexed_price_unit()

    @api.onchange('index_price_date')
    def _onchange_index_price_date(self):
        self._update_indexed_price_unit()

    def write(self, vals):
        result = super().write(vals)
        if 'index_price_date' in vals:
            self.filtered(lambda line: not line.display_type)._update_indexed_price_unit()
        return result
