import logging

from odoo import api, Command, fields, models, _
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class WeighbridgeTicket(models.Model):
    _inherit = "weighbridge.ticket"

    stock_state = fields.Selection(
        [
            ("not_applicable", "Not applicable"), ("pending", "Pending"),
            ("processing", "Processing"), ("done", "Done"),
            ("error", "Error"), ("reversed", "Reversed"),
        ],
        default="pending", required=True, readonly=True, copy=False, index=True, tracking=True,
    )
    stock_error = fields.Text(readonly=True, copy=False)
    picking_ids = fields.Many2many(
        "stock.picking", "weighbridge_ticket_picking_rel", "ticket_id", "picking_id", readonly=True, copy=False,
    )
    stock_move_ids = fields.Many2many(
        "stock.move", "weighbridge_ticket_move_rel", "ticket_id", "move_id", readonly=True, copy=False,
    )
    overdelivery_approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)

    def _quantity_in_uom(self, uom):
        self.ensure_one()
        return self.env.ref("uom.product_uom_kgm")._compute_quantity(self.payable_weight_kg, uom)

    def _is_weight_uom(self, uom):
        """Odoo 19 models UoM families through their reference-unit chain."""
        kilogram = self.env.ref("uom.product_uom_kgm")
        while kilogram.relative_uom_id:
            kilogram = kilogram.relative_uom_id
        while uom.relative_uom_id:
            uom = uom.relative_uom_id
        return uom == kilogram

    def _check_station_stock_configuration(self):
        self.ensure_one()
        station = self.station_id
        required = station.warehouse_id and station.incoming_picking_type_id and station.outgoing_picking_type_id
        required = required and station.source_location_id and station.destination_location_id
        if not required:
            raise UserError(_("Complete the station stock configuration before processing this ticket."))

    def _weighbridge_prepare_stock_line(self):
        """Commercial addons return or create their applicable order line."""
        self.ensure_one()
        raise UserError(_("Install the weighbridge integration for commercial role '%s'.", self.commercial_role))

    def _weighbridge_line_values(self, line):
        """Return planned quantity, handled quantity and UoM for an order line."""
        raise UserError(_("The selected order-line type is not supported."))

    def _validate_existing_line(self, line):
        self.ensure_one()
        planned, handled, uom = self._weighbridge_line_values(line)
        quantity = self._quantity_in_uom(uom)
        remaining = max(planned - handled, 0.0)
        allowed = planned * self.station_id.overdelivery_tolerance / 100.0
        if float_compare(quantity, remaining + allowed, precision_rounding=uom.rounding) > 0 and not self.overdelivery_approved_by_id:
            raise UserError(_("The payable quantity exceeds the remaining order quantity and requires manager approval."))
        return quantity

    def _complete_order_move(self, line):
        self.ensure_one()
        quantity = self._validate_existing_line(line)
        if self.product_id.tracking != "none":
            raise UserError(_("Tracked products require lot/serial allocation before weighbridge processing."))
        expected_code = "incoming" if self.direction == "incoming" else "outgoing"
        moves = line.move_ids.filtered(
            lambda move: move.state not in ("done", "cancel")
            and move.picking_id
            and move.picking_id.picking_type_code == expected_code
            and move.product_id == self.product_id
        )
        if not moves:
            raise UserError(_("No open stock move exists for the selected order line and physical direction."))
        move = moves.sorted("id")[0]
        quantity = self._quantity_in_uom(move.product_uom)
        picking = move.picking_id
        if float_compare(quantity, move.product_uom_qty, precision_rounding=move.product_uom.rounding) > 0:
            move.product_uom_qty = quantity
        (picking.move_ids - move).filtered(lambda item: item.state not in ("done", "cancel")).quantity = 0
        move.quantity = quantity
        move.picked = True
        result = picking.with_context(skip_sanity_check=False).button_validate()
        if isinstance(result, dict) and result.get("res_model"):
            raise UserError(_("The transfer needs additional manual input before it can be validated."))
        self.write({
            "picking_ids": [Command.link(picking.id)],
            "stock_move_ids": [Command.link(move.id)],
        })

    def _complete_no_charge(self):
        self.ensure_one()
        self._check_station_stock_configuration()
        if self.product_id.tracking != "none":
            raise UserError(_("Tracked products require lot/serial allocation before weighbridge processing."))
        station = self.station_id
        incoming = self.direction == "incoming"
        picking_type = station.incoming_picking_type_id if incoming else station.outgoing_picking_type_id
        source = station.source_location_id if incoming else station.warehouse_id.lot_stock_id
        destination = station.warehouse_id.lot_stock_id if incoming else station.destination_location_id
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id, "partner_id": self.partner_id.id,
            "location_id": source.id, "location_dest_id": destination.id, "origin": self.name,
            "move_ids": [Command.create({
                "product_id": self.product_id.id, "product_uom": self.product_id.uom_id.id,
                "product_uom_qty": self._quantity_in_uom(self.product_id.uom_id),
                "location_id": source.id, "location_dest_id": destination.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.quantity = picking.move_ids.product_uom_qty
        picking.move_ids.picked = True
        result = picking.button_validate()
        if isinstance(result, dict) and result.get("res_model"):
            raise UserError(_("The transfer needs additional manual input before it can be validated."))
        self.write({
            "picking_ids": [Command.link(picking.id)],
            "stock_move_ids": [Command.set(picking.move_ids.ids)],
        })

    def action_process_stock(self):
        self.check_access("write")
        for requested in self:
            ticket = requested.sudo()
            if ticket.state != "completed" or ticket.stock_state in ("done", "reversed", "not_applicable"):
                continue
            if ticket.stock_move_ids:
                ticket.write({"stock_state": "done", "stock_error": False})
                continue
            ticket.write({"stock_state": "processing", "stock_error": False})
            if ticket.commercial_role == "no_charge":
                ticket._complete_no_charge()
            else:
                ticket._complete_order_move(ticket._weighbridge_prepare_stock_line())
            ticket.write({"stock_state": "done", "stock_error": False})
        return True

    def action_approve_overdelivery(self):
        if not self.env.user.has_group("abfall_weighbridge.group_weighbridge_manager"):
            raise UserError(_("Only a weighbridge manager may approve over-delivery."))
        self.write({"overdelivery_approved_by_id": self.env.user.id, "stock_state": "pending", "stock_error": False})
        return self.action_process_stock()

    def action_cancel_ticket(self, reason=None):
        if any(ticket.stock_state == "done" for ticket in self):
            raise UserError(_("Reverse completed stock transfers before cancelling this ticket."))
        return super().action_cancel_ticket(reason=reason)

    @api.model
    def _cron_process_stock(self):
        tickets = self.search([("state", "=", "completed"), ("stock_state", "in", ("pending", "error"))])
        for ticket in tickets:
            try:
                with self.env.cr.savepoint():
                    ticket.action_process_stock()
            except Exception as error:  # cron must isolate tickets and retain a retryable error
                ticket.write({"stock_state": "error", "stock_error": str(error)})
                _logger.exception("Weighbridge stock processing failed for ticket %s", ticket.id)
