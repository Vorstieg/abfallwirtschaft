import base64
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..models.challenge import crc16_modbus


@tagged("post_install", "-at_install")
class TestWeighbridgeCapture(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = new_test_user(cls.env, "wb_operator", groups="abfall_weighbridge.group_weighbridge_operator")
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Weighbridge Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Bulk material", "uom_id": cls.env.ref("uom.product_uom_kgm").id,
        })
        cls.station = cls.env["weighbridge.station"].create({
            "name": "Test Bridge", "code": "WB-TEST", "company_id": cls.company.id,
            "edge_url": "https://bridge.test:8443", "terminal_number": "001", "scale_number": "1",
            "shared_secret": "test-secret-with-more-than-thirty-two-characters",
        })

    def _ticket(self, **extra):
        return self.env["weighbridge.ticket"].create({
            "station_id": self.station.id, "partner_id": self.partner.id, "product_id": self.product.id,
            "direction": "incoming", "commercial_role": "no_charge", **extra,
        })

    def _frame(self, gross, archive_id):
        now = fields.Datetime.now()
        values = [
            "00", "00", now.strftime("%d.%m.%y"), now.strftime("%H:%M"), str(archive_id).rjust(4), "1",
            f"{gross:.2f}".rjust(8), "0.00".rjust(8), f"{gross:.2f}".rjust(8), "kg", "  ", "1", "001",
        ]
        prefix = "".join(values).encode()
        return prefix + str(crc16_modbus(prefix)).rjust(8).encode() + b"\r\n", now

    def _capture(self, ticket, gross, archive_id):
        Challenge = self.env["weighbridge.capture.challenge"].with_user(self.operator)
        issued = Challenge.issue(ticket.id, self.station.id)
        token = self.station._decode_token(issued["challenge"])
        raw, timestamp = self._frame(gross, archive_id)
        parsed_crc = raw.rstrip()[-8:].decode().strip()
        payload = {
            "protocol_version": "1", "capture_uuid": f"capture-{ticket.id}-{archive_id}",
            "challenge_uuid": token["challenge_uuid"], "station": self.station.code,
            "terminal_number": "001", "scale_number": "1", "terminal_timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:00"),
            "archive_mode": "asm", "archive_id": str(archive_id), "gross": f"{gross:.2f}",
            "tare": "0.00", "net": f"{gross:.2f}", "unit": "kg", "tare_code": "",
            "weighing_range": "1", "scale_status": "00", "it3_crc16": parsed_crc,
            "raw_response": base64.b64encode(raw).decode(), "edge_received_at": fields.Datetime.now().isoformat() + "Z",
        }
        payload["signature"] = self.station._sign(payload)
        return Challenge, issued["challenge"], payload

    def test_two_stage_capture_completes_without_integrations(self):
        ticket = self._ticket()
        challenge, token, capture = self._capture(ticket, 2000, 1)
        result = challenge.commit(token, capture)
        self.assertEqual(result["ticket_state"], "first_weighed")
        challenge, token, capture = self._capture(ticket, 1250, 2)
        result = challenge.commit(token, capture)
        self.assertEqual(result["ticket_state"], "completed")
        self.assertEqual(ticket.measured_net_kg, 750)
        self.assertEqual(ticket.payable_weight_kg, 750)

    def test_challenge_replay_and_measurement_immutability(self):
        ticket = self._ticket()
        challenge, token, capture = self._capture(ticket, 1000, 10)
        challenge.commit(token, capture)
        with self.assertRaisesRegex(ValidationError, "already consumed"):
            challenge.commit(token, capture)
        with self.assertRaises(UserError):
            ticket.first_measurement_id.write({"gross_text": "999"})
        with self.assertRaises(UserError):
            ticket.first_measurement_id.unlink()

    def test_expiry_signature_tamper_and_archive_zero(self):
        ticket = self._ticket()
        challenge, token, capture = self._capture(ticket, 1000, 11)
        record = challenge.search([("uuid", "=", capture["challenge_uuid"])])
        record.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        with self.assertRaisesRegex(ValidationError, "expired"):
            challenge.commit(token, capture)

        ticket = self._ticket()
        challenge, token, capture = self._capture(ticket, 1000, 12)
        capture["gross"] = "999.00"
        with self.assertRaisesRegex(ValidationError, "signature"):
            challenge.commit(token, capture)

        ticket = self._ticket()
        challenge, token, capture = self._capture(ticket, 1000, 0)
        with self.assertRaisesRegex(ValidationError, "Archive ID zero"):
            challenge.commit(token, capture)

    def test_secret_field_is_restricted(self):
        station = self.station.with_user(self.operator)
        with self.assertRaises(AccessError):
            station.read(["shared_secret"])

    def test_loopback_http_edge_is_development_only(self):
        self.station.edge_url = "http://127.0.0.1:8443"
        with self.assertRaisesRegex(ValidationError, "HTTPS"):
            self.station.edge_url = "http://edge.example.test:8443"

    def test_deductions_drive_payable_weight(self):
        ticket = self._ticket(deduction_ids=[Command.create({"kind": "fixed", "value": 100, "reason": "Moisture"})])
        challenge, token, capture = self._capture(ticket, 2000, 20)
        challenge.commit(token, capture)
        challenge, token, capture = self._capture(ticket, 1000, 21)
        challenge.commit(token, capture)
        self.assertEqual(ticket.measured_net_kg, 1000)
        self.assertEqual(ticket.payable_weight_kg, 900)
