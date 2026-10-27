from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


FINAL_STATES = ("completed", "cancelled")


class WeighbridgeDeduction(models.Model):
    _name = "weighbridge.deduction"
    _description = "Weighbridge Weight Deduction"
    _order = "id"

    ticket_id = fields.Many2one("weighbridge.ticket", required=True, ondelete="cascade", index=True)
    kind = fields.Selection([("percent", "Percentage"), ("fixed", "Fixed kg")], required=True, default="percent")
    value = fields.Float(required=True)
    amount_kg = fields.Float(compute="_compute_amount", store=True, digits=(16, 3))
    reason = fields.Char(required=True)
    approved_by_id = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)

    @api.depends("kind", "value", "ticket_id.measured_net_kg")
    def _compute_amount(self):
        for deduction in self:
            deduction.amount_kg = (
                deduction.ticket_id.measured_net_kg * deduction.value / 100.0
                if deduction.kind == "percent" else deduction.value
            )

    @api.constrains("value")
    def _check_value(self):
        if any(d.value < 0 or (d.kind == "percent" and d.value > 100) for d in self):
            raise ValidationError(_("A deduction must be non-negative and percentages cannot exceed 100."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ticket = self.env["weighbridge.ticket"].browse(vals.get("ticket_id"))
            if ticket.state in FINAL_STATES:
                raise UserError(_("Deductions cannot be changed after the second weighing."))
            vals.update(approved_by_id=self.env.user.id, approved_at=fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        if any(d.ticket_id.state in FINAL_STATES for d in self):
            raise UserError(_("Deductions cannot be changed after the second weighing."))
        vals.update(approved_by_id=self.env.user.id, approved_at=fields.Datetime.now())
        return super().write(vals)

    def unlink(self):
        if any(d.ticket_id.state in FINAL_STATES for d in self):
            raise UserError(_("Deductions cannot be changed after the second weighing."))
        return super().unlink()


class WeighbridgeTicket(models.Model):
    _name = "weighbridge.ticket"
    _description = "Weighbridge Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, index=True)
    station_id = fields.Many2one("weighbridge.station", required=True, ondelete="restrict", tracking=True, check_company=True)
    company_id = fields.Many2one(related="station_id.company_id", store=True, index=True)
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    product_id = fields.Many2one("product.product", required=True, tracking=True, domain="[('type', '!=', 'service')]")
    direction = fields.Selection([("incoming", "Incoming"), ("outgoing", "Outgoing")], required=True, tracking=True)
    commercial_role = fields.Selection(
        [("purchase", "Purchase"), ("sale", "Sale"), ("no_charge", "No charge")],
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("first_weighed", "First weighed"), ("completed", "Completed"), ("cancelled", "Cancelled")],
        default="draft", required=True, readonly=True, index=True, tracking=True,
    )
    measurement_ids = fields.One2many("weighbridge.measurement", "ticket_id", readonly=True)
    first_measurement_id = fields.Many2one("weighbridge.measurement", compute="_compute_measurements", store=True)
    second_measurement_id = fields.Many2one("weighbridge.measurement", compute="_compute_measurements", store=True)
    measured_net_kg = fields.Float(compute="_compute_weights", store=True, digits=(16, 3))
    deduction_ids = fields.One2many("weighbridge.deduction", "ticket_id")
    deduction_kg = fields.Float(compute="_compute_weights", store=True, digits=(16, 3))
    payable_weight_kg = fields.Float(compute="_compute_weights", store=True, digits=(16, 3))
    cancellation_reason = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            if ticket.name == "New":
                ticket.name = ticket.station_id.sequence_id.next_by_id()
        return tickets

    @api.depends("measurement_ids", "measurement_ids.position")
    def _compute_measurements(self):
        for ticket in self:
            ticket.first_measurement_id = ticket.measurement_ids.filtered(lambda m: m.position == "first")[:1]
            ticket.second_measurement_id = ticket.measurement_ids.filtered(lambda m: m.position == "second")[:1]

    @api.depends("first_measurement_id.gross_kg", "second_measurement_id.gross_kg", "deduction_ids.amount_kg")
    def _compute_weights(self):
        for ticket in self:
            if ticket.first_measurement_id and ticket.second_measurement_id:
                ticket.measured_net_kg = abs(ticket.first_measurement_id.gross_kg - ticket.second_measurement_id.gross_kg)
            else:
                ticket.measured_net_kg = 0.0
            ticket.deduction_kg = sum(ticket.deduction_ids.mapped("amount_kg"))
            ticket.payable_weight_kg = ticket.measured_net_kg - ticket.deduction_kg

    def write(self, vals):
        protected = {"station_id", "partner_id", "product_id", "direction", "commercial_role"}
        if not self.env.context.get("weighbridge_internal") and protected.intersection(vals) and any(t.state != "draft" for t in self):
            raise UserError(_("Core ticket data is immutable after the first weighing."))
        return super().write(vals)

    def unlink(self):
        if any(t.state not in ("draft", "cancelled") or t.measurement_ids for t in self):
            raise UserError(_("Weighed tickets cannot be deleted; cancel them instead."))
        return super().unlink()

    def _accept_measurement(self, measurement):
        """Accept certified evidence only; optional ERP processing happens later."""
        self.ensure_one()
        expected = "first" if self.state == "draft" else "second" if self.state == "first_weighed" else False
        if not expected or measurement.position != expected:
            raise UserError(_("The measurement position does not match the ticket state."))
        if expected == "first":
            self.with_context(weighbridge_internal=True).write({"state": "first_weighed"})
            return
        self.invalidate_recordset([
            "measurement_ids", "first_measurement_id", "second_measurement_id",
            "measured_net_kg", "deduction_kg", "payable_weight_kg",
        ])
        self._compute_measurements()
        self._compute_weights()
        if self.payable_weight_kg <= 0 or self.deduction_kg > self.measured_net_kg:
            raise UserError(_("Payable weight must be positive and deductions cannot exceed measured net weight."))
        self.with_context(weighbridge_internal=True).write({"state": "completed"})

    def action_cancel_ticket(self, reason=None):
        for ticket in self:
            ticket.with_context(weighbridge_internal=True).write({
                "state": "cancelled",
                "cancellation_reason": reason or _("Cancelled by %s", self.env.user.display_name),
            })
