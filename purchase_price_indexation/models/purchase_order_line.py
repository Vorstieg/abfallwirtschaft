from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _compute_price_unit_and_date_planned_and_name(self):
        super()._compute_price_unit_and_date_planned_and_name()

        for line in self:
            requisition = line.order_id.requisition_id
            if not requisition or not line.product_id or line.display_type:
                continue

            req_lines = requisition.line_ids.filtered(lambda l: l.product_id == line.product_id)
            if not req_lines:
                continue

            req_line = req_lines.filtered(lambda l: l.product_uom_id == line.product_uom_id)[:1] or req_lines[:1]
            req_line = req_line[:1]
            if not req_line or not req_line.is_indexed_price:
                continue

            # Recompute at RFQ/PO context date so indexed contracts do not fallback to stale base price.
            target_date = (line.order_id.date_order and fields.Datetime.to_datetime(line.order_id.date_order).date()) or fields.Date.context_today(line)
            line.price_unit = req_line.product_uom_id._compute_price(req_line._get_indexed_price(target_date), line.product_uom_id)
