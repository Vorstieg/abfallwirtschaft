import logging
from collections import defaultdict
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class WeighbridgeStation(models.Model):
    _inherit = "weighbridge.station"

    billing_mode = fields.Selection([("immediate", "Immediate"), ("monthly", "Monthly")], default="monthly", required=True)
    billing_day = fields.Integer(default=1, required=True)

    @api.constrains("billing_day")
    def _check_billing_day(self):
        if any(not 1 <= station.billing_day <= 28 for station in self):
            raise ValidationError(_("Billing day must be between 1 and 28."))


class WeighbridgeBillingProfile(models.Model):
    _name = "weighbridge.billing.profile"
    _description = "Weighbridge Billing Profile"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    partner_id = fields.Many2one("res.partner", domain="[('is_company', '=', True)]")
    commercial_role = fields.Selection([("purchase", "Purchase"), ("sale", "Sale")], required=True)
    billing_mode = fields.Selection([("immediate", "Immediate"), ("monthly", "Monthly")], required=True, default="monthly")
    billing_day = fields.Integer(default=1, required=True)

    @api.constrains("billing_day")
    def _check_day(self):
        if any(not 1 <= profile.billing_day <= 28 for profile in self):
            raise ValidationError(_("Billing day must be between 1 and 28."))

    def _local_today(self):
        self.ensure_one()
        timezone = ZoneInfo(self.company_id.partner_id.tz or "UTC")
        return fields.Datetime.now().replace(tzinfo=ZoneInfo("UTC")).astimezone(timezone).date()

    def _invoice_group_key(self, ticket):
        if ticket.commercial_role == "sale":
            order = ticket.sale_order_id or ticket.sale_line_id.order_id
            return (
                ticket.company_id.id, ticket.partner_id.commercial_partner_id.id,
                order.partner_invoice_id.id, ticket.commercial_role, order.currency_id.id,
                order.fiscal_position_id.id, order.payment_term_id.id,
            )
        order = ticket.purchase_order_id or ticket.purchase_line_id.order_id
        return (
            ticket.company_id.id, ticket.partner_id.commercial_partner_id.id,
            order.partner_id.id, ticket.commercial_role, order.currency_id.id,
            order.fiscal_position_id.id, order.payment_term_id.id,
        )

    def _invoice_ticket_group(self, tickets):
        existing = tickets.mapped("invoice_ids").filtered(lambda move: move.state != "cancel")
        tickets = tickets.filtered(lambda ticket: not ticket.invoice_ids.filtered(lambda move: move.state != "cancel"))
        if not tickets:
            return existing
        if tickets[0].commercial_role == "sale":
            invoices = tickets.mapped("sale_line_id.order_id")._create_invoices(grouped=False)
        else:
            orders = tickets.mapped("purchase_line_id.order_id")
            previous = orders.mapped("invoice_ids")
            orders.action_create_invoice()
            invoices = orders.mapped("invoice_ids") - previous
        for ticket in tickets:
            lines = invoices.invoice_line_ids.filtered(
                lambda line: line.sale_line_ids & ticket.sale_line_id or line.purchase_line_id == ticket.purchase_line_id
            )
            ticket.write({
                "invoice_ids": [Command.link(move.id) for move in lines.move_id],
                "billing_state": "allocated_draft",
                "billing_error": False,
            })
            lines.write({"weighbridge_ticket_ids": [Command.link(ticket.id)]})
        return invoices | existing

    @api.model
    def _cron_billing(self):
        immediate = self.env["weighbridge.ticket"].search([
            ("state", "=", "completed"), ("stock_state", "=", "done"),
            ("billing_mode", "=", "immediate"), ("billing_state", "in", ("pending", "error")),
        ])
        for ticket in immediate:
            try:
                with self.env.cr.savepoint():
                    ticket._create_and_link_invoice(post=True)
            except Exception as error:
                ticket.write({"billing_state": "error", "billing_error": str(error)})
                _logger.exception("Immediate weighbridge billing failed for ticket %s", ticket.id)

        profiles = self.search([
            ("active", "=", True), ("billing_mode", "=", "monthly"),
            ("commercial_role", "in", ("sale", "purchase")),
        ])
        for profile in profiles:
            today = profile._local_today()
            if today.day != profile.billing_day:
                continue
            period_end = today.replace(day=1) - relativedelta(days=1)
            period_start = period_end.replace(day=1)
            domain = [
                ("company_id", "=", profile.company_id.id), ("commercial_role", "=", profile.commercial_role),
                ("billing_mode", "=", "monthly"), ("billing_state", "in", ("pending", "error")),
                ("state", "=", "completed"), ("stock_state", "=", "done"),
                ("second_measurement_id.terminal_date", ">=", period_start),
                ("second_measurement_id.terminal_date", "<=", period_end),
            ]
            if profile.partner_id:
                domain.append(("partner_id", "child_of", profile.partner_id.commercial_partner_id.id))
            groups = defaultdict(lambda: self.env["weighbridge.ticket"])
            for ticket in self.env["weighbridge.ticket"].search(domain):
                groups[profile._invoice_group_key(ticket)] |= ticket
            for tickets in groups.values():
                try:
                    with self.env.cr.savepoint():
                        profile._invoice_ticket_group(tickets)
                except Exception as error:
                    tickets.write({"billing_state": "error", "billing_error": str(error)})
                    _logger.exception("Monthly weighbridge billing failed for ticket IDs %s", tickets.ids)

    @api.model
    def _cron_monthly_billing(self):
        """Compatibility entry point for cron records from the combined addon."""
        return self._cron_billing()


class WeighbridgeTicket(models.Model):
    _inherit = "weighbridge.ticket"

    billing_mode = fields.Selection([("immediate", "Immediate"), ("monthly", "Monthly")], required=True, default="monthly", tracking=True)
    billing_state = fields.Selection(
        [
            ("not_applicable", "Not applicable"), ("pending", "Pending"),
            ("allocated_draft", "Allocated to draft"), ("posted", "Posted"),
            ("error", "Error"), ("reversed", "Reversed"),
        ],
        default="pending", required=True, readonly=True, copy=False, index=True, tracking=True,
    )
    billing_error = fields.Text(readonly=True, copy=False)
    invoice_ids = fields.Many2many(
        "account.move", "weighbridge_ticket_invoice_rel", "ticket_id", "move_id", readonly=True, copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket, values in zip(tickets, vals_list):
            if ticket.commercial_role == "no_charge":
                ticket.billing_state = "not_applicable"
                continue
            if "billing_mode" not in values:
                profile = ticket._billing_profile()
                ticket.billing_mode = profile.billing_mode or ticket.station_id.billing_mode
        return tickets

    def _billing_profile(self):
        self.ensure_one()
        return self.env["weighbridge.billing.profile"].search([
            ("company_id", "=", self.company_id.id), ("commercial_role", "=", self.commercial_role),
            "|", ("partner_id", "=", self.partner_id.commercial_partner_id.id), ("partner_id", "=", False),
        ], order="partner_id desc, sequence, id", limit=1)

    def _create_and_link_invoice(self, post=False):
        self.ensure_one()
        if self.state != "completed" or self.stock_state != "done":
            raise UserError(_("Stock processing must finish before billing."))
        invoices = self.invoice_ids.filtered(lambda move: move.state != "cancel")
        if not invoices:
            if self.commercial_role == "sale":
                invoices = (self.sale_order_id or self.sale_line_id.order_id)._create_invoices(grouped=True)
            elif self.commercial_role == "purchase":
                order = self.purchase_order_id or self.purchase_line_id.order_id
                previous = order.invoice_ids
                order.action_create_invoice()
                invoices = order.invoice_ids - previous
            else:
                self.billing_state = "not_applicable"
                return self.env["account.move"]
        self.invoice_ids = [Command.link(invoice.id) for invoice in invoices]
        relevant = invoices.invoice_line_ids.filtered(
            lambda line: line.sale_line_ids & self.sale_line_id or line.purchase_line_id == self.purchase_line_id
        )
        relevant.write({"weighbridge_ticket_ids": [Command.link(self.id)]})
        if post:
            invoices.filtered(lambda move: move.state == "draft").action_post()
        self.write({
            "billing_state": "posted" if invoices and all(move.state == "posted" for move in invoices) else "allocated_draft",
            "billing_error": False,
        })
        return invoices

    def action_process_billing(self):
        if not self.env.user.has_group("abfall_weighbridge_billing.group_weighbridge_accounting"):
            raise UserError(_("Only weighbridge accounting users may process billing manually."))
        for ticket in self:
            ticket.sudo()._create_and_link_invoice(post=ticket.billing_mode == "immediate")
        return True

    def action_cancel_ticket(self, reason=None):
        if any(ticket.billing_state in ("allocated_draft", "posted") for ticket in self):
            raise UserError(_("Cancel or reverse accounting documents before cancelling this ticket."))
        return super().action_cancel_ticket(reason=reason)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    weighbridge_ticket_ids = fields.Many2many(
        "weighbridge.ticket", "weighbridge_ticket_invoice_line_rel", "line_id", "ticket_id",
        string="Weighbridge Tickets", copy=False,
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        result = super().action_post()
        tickets = self.invoice_line_ids.weighbridge_ticket_ids
        for ticket in tickets:
            active = ticket.invoice_ids.filtered(lambda move: move.state != "cancel")
            if active and all(move.state == "posted" for move in active):
                ticket.billing_state = "posted"
        return result

    def _reverse_moves(self, default_values_list=None, cancel=False):
        reversals = super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)
        for source, reversal in zip(self, reversals):
            tickets = source.invoice_line_ids.weighbridge_ticket_ids
            reversal.invoice_line_ids.write({"weighbridge_ticket_ids": [Command.set(tickets.ids)]})
            for ticket in tickets:
                ticket.write({"invoice_ids": [Command.link(reversal.id)], "billing_state": "reversed"})
        return reversals
