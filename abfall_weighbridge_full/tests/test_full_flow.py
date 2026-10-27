import base64

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestWeighbridgeFullFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.partner = cls.env["res.partner"].create({"name": "Full Flow Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Full Flow Bulk Material", "is_storable": True,
            "uom_id": cls.env.ref("uom.product_uom_kgm").id,
        })
        cls.receivable = cls.env["account.account"].create({
            "name": "WB Test Receivable", "code": "WB1100", "account_type": "asset_receivable",
            "company_ids": [Command.set(cls.company.ids)], "reconcile": True,
        })
        cls.payable = cls.env["account.account"].create({
            "name": "WB Test Payable", "code": "WB3300", "account_type": "liability_payable",
            "company_ids": [Command.set(cls.company.ids)], "reconcile": True,
        })
        cls.income = cls.env["account.account"].create({
            "name": "WB Test Income", "code": "WB4000", "account_type": "income",
            "company_ids": [Command.set(cls.company.ids)],
        })
        cls.expense = cls.env["account.account"].create({
            "name": "WB Test Expense", "code": "WB5000", "account_type": "expense",
            "company_ids": [Command.set(cls.company.ids)],
        })
        cls.partner.with_company(cls.company).write({
            "property_account_receivable_id": cls.receivable.id,
            "property_account_payable_id": cls.payable.id,
        })
        cls.product.product_tmpl_id.with_company(cls.company).write({
            "property_account_income_id": cls.income.id,
            "property_account_expense_id": cls.expense.id,
        })
        cls.env["account.journal"].create({
            "name": "WB Test Sales", "code": "WBS", "type": "sale", "company_id": cls.company.id,
        })
        cls.env["account.journal"].create({
            "name": "WB Test Purchases", "code": "WBP", "type": "purchase", "company_id": cls.company.id,
        })
        cls.station = cls.env["weighbridge.station"].create({
            "name": "Full Flow Bridge", "code": "WB-FULL", "company_id": cls.company.id,
            "warehouse_id": cls.warehouse.id,
            "incoming_picking_type_id": cls.warehouse.in_type_id.id,
            "outgoing_picking_type_id": cls.warehouse.out_type_id.id,
            "source_location_id": cls.env.ref("stock.stock_location_suppliers").id,
            "destination_location_id": cls.env.ref("stock.stock_location_customers").id,
            "edge_url": "https://bridge.test:8443", "terminal_number": "001", "scale_number": "1",
            "shared_secret": "test-secret-with-more-than-thirty-two-characters",
        })

    def _complete_ticket(self, role, direction, sequence):
        ticket = self.env["weighbridge.ticket"].create({
            "station_id": self.station.id, "partner_id": self.partner.id,
            "product_id": self.product.id, "direction": direction, "commercial_role": role,
        })
        for position, gross, offset in (("first", 1000.0, 0), ("second", 500.0, 1)):
            now = fields.Datetime.now()
            measurement = self.env["weighbridge.measurement"].with_context(
                weighbridge_verified_capture=True
            ).create({
                "ticket_id": ticket.id, "station_id": self.station.id, "position": position,
                "protocol_version": "1", "capture_uuid": f"full-{sequence}-{offset}",
                "challenge_uuid": f"challenge-{sequence}-{offset}", "terminal_number": "001",
                "scale_number": "1", "terminal_timestamp": now, "terminal_date": now.date(),
                "archive_mode": "asm", "archive_id": str(sequence + offset),
                "gross_text": f"{gross:.2f}", "tare_text": "0.00", "net_text": f"{gross:.2f}",
                "gross_kg": gross, "tare_kg": 0.0, "net_kg": gross, "unit": "kg",
                "tare_code": "", "weighing_range": "1", "scale_status": "00", "it3_crc16": "1",
                "raw_response": base64.b64encode(b"test"), "edge_received_at": now,
                "edge_signature": "test-signature",
            })
            ticket._accept_measurement(measurement)
        self.assertEqual(ticket.state, "completed")
        self.assertEqual(ticket.payable_weight_kg, 500.0)
        return ticket

    def test_no_charge_stock_is_independent(self):
        ticket = self._complete_ticket("no_charge", "incoming", 100)
        ticket.action_process_stock()
        self.assertEqual(ticket.state, "completed")
        self.assertEqual(ticket.stock_state, "done")
        self.assertEqual(ticket.picking_ids.state, "done")
        self.assertEqual(ticket.billing_state, "not_applicable")

    def test_spot_sale_uses_order_delivery(self):
        ticket = self._complete_ticket("sale", "outgoing", 200)
        ticket.action_process_stock()
        self.assertEqual(ticket.stock_state, "done")
        self.assertTrue(ticket.sale_order_id)
        self.assertEqual(ticket.picking_ids, ticket.sale_order_id.picking_ids.filtered(lambda picking: picking.state == "done"))

    def test_spot_purchase_uses_order_receipt(self):
        ticket = self._complete_ticket("purchase", "incoming", 300)
        ticket.action_process_stock()
        self.assertEqual(ticket.stock_state, "done")
        self.assertTrue(ticket.purchase_order_id)
        self.assertEqual(ticket.picking_ids, ticket.purchase_order_id.picking_ids.filtered(lambda picking: picking.state == "done"))

    def test_billing_allocates_draft_after_stock(self):
        ticket = self._complete_ticket("sale", "outgoing", 400)
        ticket.action_process_stock()
        ticket._create_and_link_invoice(post=False)
        self.assertEqual(ticket.billing_state, "allocated_draft")
        self.assertTrue(ticket.invoice_ids)
        self.assertTrue(ticket.invoice_ids.invoice_line_ids.weighbridge_ticket_ids & ticket)

    def test_immediate_billing_posts_without_payment(self):
        ticket = self._complete_ticket("sale", "outgoing", 500)
        ticket.billing_mode = "immediate"
        ticket.action_process_stock()
        ticket._create_and_link_invoice(post=True)
        self.assertEqual(ticket.billing_state, "posted")
        self.assertEqual(ticket.invoice_ids.state, "posted")
        self.assertFalse(ticket.invoice_ids.payment_state == "paid")

    def test_monthly_grouping_is_idempotent(self):
        first = self._complete_ticket("sale", "outgoing", 600)
        second = self._complete_ticket("sale", "outgoing", 700)
        (first | second).action_process_stock()
        profile = self.env["weighbridge.billing.profile"].create({
            "name": "Test monthly sales", "company_id": self.company.id,
            "commercial_role": "sale", "billing_mode": "monthly", "billing_day": 1,
        })
        invoices = profile._invoice_ticket_group(first | second)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(first.billing_state, "allocated_draft")
        self.assertEqual(second.billing_state, "allocated_draft")
        self.assertEqual(profile._invoice_ticket_group(first | second), invoices)
