from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class WeighbridgeTicket(models.Model):
    _inherit = "weighbridge.ticket"

    sale_line_id = fields.Many2one("sale.order.line", ondelete="restrict", check_company=True)
    sale_order_id = fields.Many2one("sale.order", readonly=True, check_company=True, copy=False)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    price_unit = fields.Monetary()
    manual_price = fields.Boolean(tracking=True)
    manual_price_reason = fields.Char(tracking=True)

    @api.constrains("manual_price", "manual_price_reason", "commercial_role")
    def _check_sale_manual_price_reason(self):
        if any(ticket.commercial_role == "sale" and ticket.manual_price and not ticket.manual_price_reason for ticket in self):
            raise ValidationError(_("A reason is required for a manual sales price override."))

    @api.constrains("sale_line_id", "commercial_role", "product_id", "partner_id")
    def _check_sale_line(self):
        for ticket in self.filtered("sale_line_id"):
            line = ticket.sale_line_id
            if ticket.commercial_role != "sale":
                raise ValidationError(_("A sales line requires the Sale commercial role."))
            if line.product_id != ticket.product_id or line.order_id.company_id != ticket.company_id:
                raise ValidationError(_("Sales line product or company does not match the ticket."))
            if line.order_id.partner_id.commercial_partner_id != ticket.partner_id.commercial_partner_id:
                raise ValidationError(_("Sales line partner does not match the ticket partner."))
            if not ticket._is_weight_uom(line.product_uom_id):
                raise ValidationError(_("The selected sales line must use a weight unit."))

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket, values in zip(tickets, vals_list):
            if ticket.sale_line_id and not values.get("manual_price"):
                ticket.write({"price_unit": ticket.sale_line_id.price_unit, "currency_id": ticket.sale_line_id.currency_id.id})
        return tickets

    def write(self, vals):
        if not self.env.context.get("weighbridge_commercial_internal") and "sale_line_id" in vals and any(ticket.state != "draft" for ticket in self):
            raise UserError(_("The sales line is immutable after the first weighing."))
        return super().write(vals)

    def _spot_sale(self):
        self.ensure_one()
        self._check_station_stock_configuration()
        order = self.env["sale.order"].create({
            "partner_id": self.partner_id.id, "company_id": self.company_id.id,
            "warehouse_id": self.station_id.warehouse_id.id,
        })
        values = {
            "order_id": order.id, "product_id": self.product_id.id,
            "product_uom_qty": self._quantity_in_uom(self.product_id.uom_id),
            "product_uom_id": self.product_id.uom_id.id,
        }
        if self.manual_price:
            if not self.manual_price_reason:
                raise UserError(_("A reason is required for a manual price override."))
            values["price_unit"] = self.price_unit
        line = self.env["sale.order.line"].create(values)
        order.action_confirm()
        self.with_context(weighbridge_commercial_internal=True).write({
            "sale_order_id": order.id, "sale_line_id": line.id,
            "price_unit": line.price_unit, "currency_id": order.currency_id.id,
        })
        return line

    def _weighbridge_prepare_stock_line(self):
        self.ensure_one()
        if self.commercial_role != "sale":
            return super()._weighbridge_prepare_stock_line()
        line = self.sale_line_id or self._spot_sale()
        if line.order_id.state not in ("sale", "done"):
            raise UserError(_("The selected sales order must be confirmed."))
        return line

    def _weighbridge_line_values(self, line):
        if line._name == "sale.order.line":
            return line.product_uom_qty, line.qty_delivered, line.product_uom_id
        return super()._weighbridge_line_values(line)
