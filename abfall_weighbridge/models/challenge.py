import base64
import binascii
from datetime import datetime, timedelta, timezone
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


SUPPORTED_UNITS = {"kg": 1.0, "g": 0.001, "t": 1000.0}


def _edge_datetime(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValidationError(_("Malformed edge receipt timestamp.")) from error
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _index in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def _decimal(text, separator):
    normalized = text.strip().replace(separator, ".")
    try:
        return float(normalized)
    except ValueError as error:
        raise ValidationError(_("Malformed IT3 weight field: %s", text)) from error


def parse_rn_frame(raw, station):
    """Parse SysTec ONLINE RN fixed-width data and verify its trailing CRC16."""
    data = raw.rstrip(b"\r\n\0")
    if data.startswith(b"\x02"):
        data = data[1:]
    if data.endswith(b"\x03"):
        data = data[:-1]
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValidationError(_("The IT3 response is not ASCII.")) from error
    date_len = len(datetime.now().strftime(station.terminal_date_format))
    time_len = len(datetime.now().strftime(station.terminal_time_format))
    archive_len = int(station.archive_id_length)
    lengths = [2, 2, date_len, time_len, archive_len, 1, 8, 8, 8, 2, 2, 1, 3, 8]
    expected = sum(lengths)
    if ";" in text:
        parts = text.split(";")
        if len(parts) != len(lengths) or any(len(value) != length for value, length in zip(parts, lengths)):
            raise ValidationError(_("Unexpected IT3 RN separated field lengths."))
        iterator = iter(parts)
        def take(_length):
            return next(iterator)
    else:
        if len(text) != expected:
            raise ValidationError(_("Unexpected IT3 RN length: got %s, expected %s.", len(text), expected))
        offset = 0
        def take(length):
            nonlocal offset
            value = text[offset:offset + length]
            offset += length
            return value
    result = {
        "error_code": take(2), "scale_status": take(2), "date": take(date_len),
        "time": take(time_len), "archive_id": take(archive_len), "scale_number": take(1),
        "gross_text": take(8), "tare_text": take(8), "net_text": take(8),
        "unit": take(2).strip(), "tare_code": take(2).strip(), "weighing_range": take(1).strip(),
        "terminal_number": take(3), "crc": take(8).strip(),
    }
    if result["error_code"] != "00":
        raise ValidationError(_("IT3 returned error %s.", result["error_code"]))
    if result["scale_status"] != "00":
        raise ValidationError(_("IT3 weight is not settled and positive (status %s).", result["scale_status"]))
    if result["terminal_number"] != station.terminal_number or result["scale_number"] != station.scale_number:
        raise ValidationError(_("IT3 terminal or scale identity mismatch."))
    if result["unit"] not in SUPPORTED_UNITS:
        raise ValidationError(_("Unsupported IT3 weight unit: %s", result["unit"]))
    prefix = data[:-8]
    calculated = crc16_modbus(prefix)
    try:
        supplied = int(result["crc"], 16 if any(c in "abcdefABCDEF" for c in result["crc"]) else 10)
    except ValueError as error:
        raise ValidationError(_("Malformed IT3 CRC field.")) from error
    if supplied != calculated:
        raise ValidationError(_("IT3 CRC mismatch."))
    multiplier = SUPPORTED_UNITS[result["unit"]]
    result.update({
        "gross_kg": _decimal(result["gross_text"], station.decimal_separator) * multiplier,
        "tare_kg": _decimal(result["tare_text"], station.decimal_separator) * multiplier,
        "net_kg": _decimal(result["net_text"], station.decimal_separator) * multiplier,
    })
    try:
        result["terminal_datetime"] = datetime.strptime(
            result["date"] + " " + result["time"],
            station.terminal_date_format + " " + station.terminal_time_format,
        )
    except ValueError as error:
        raise ValidationError(_("Malformed IT3 terminal date or time.")) from error
    return result


class WeighbridgeCaptureChallenge(models.Model):
    _name = "weighbridge.capture.challenge"
    _description = "Single-use Weighbridge Capture Challenge"
    _order = "id desc"
    _check_company_auto = True

    uuid = fields.Char(required=True, index=True, readonly=True)
    station_id = fields.Many2one("weighbridge.station", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="station_id.company_id", store=True, index=True)
    ticket_id = fields.Many2one("weighbridge.ticket", required=True, ondelete="cascade", check_company=True)
    position = fields.Selection([("first", "First"), ("second", "Second")], required=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    expires_at = fields.Datetime(required=True, index=True)
    consumed_at = fields.Datetime(readonly=True)

    _uuid_uniq = models.Constraint("unique(uuid)", "Challenge UUID must be unique.")

    @api.model
    def issue(self, ticket_id, station_id=None):
        if not self.env.user.has_group("abfall_weighbridge.group_weighbridge_operator"):
            raise AccessError(_("Only weighbridge operators may capture measurements."))
        ticket = self.env["weighbridge.ticket"].browse(int(ticket_id)).exists()
        if not ticket:
            raise UserError(_("Ticket not found."))
        ticket.check_access("read")
        station = ticket.station_id
        if station_id and station.id != int(station_id):
            raise UserError(_("Ticket and station do not match."))
        position = "first" if ticket.state == "draft" else "second" if ticket.state == "first_weighed" else False
        if not position:
            raise UserError(_("This ticket is not ready for another measurement."))
        now = fields.Datetime.now()
        challenge = self.create({
            "uuid": str(uuid.uuid4()), "station_id": station.id, "ticket_id": ticket.id,
            "position": position, "user_id": self.env.user.id, "expires_at": now + timedelta(seconds=30),
        })
        payload = {
            "v": 1, "challenge_uuid": challenge.uuid, "station": station.code,
            "terminal": station.terminal_number, "scale": station.scale_number,
            "ticket_id": ticket.id, "position": position, "user_id": self.env.user.id,
            "exp": int((datetime.now(timezone.utc) + timedelta(seconds=30)).timestamp()),
        }
        return {"challenge": station._issue_token(payload), "edge_url": station.edge_url, "position": position}

    @api.model
    def commit(self, challenge_token, capture):
        if not self.env.user.has_group("abfall_weighbridge.group_weighbridge_operator"):
            raise AccessError(_("Only weighbridge operators may capture measurements."))
        if not isinstance(capture, dict):
            raise ValidationError(_("Malformed edge capture."))
        challenge_uuid = capture.get("challenge_uuid")
        challenge = self.search([("uuid", "=", challenge_uuid)], limit=1)
        if not challenge:
            raise ValidationError(_("Unknown capture challenge."))
        self.env.cr.execute("SELECT id FROM weighbridge_capture_challenge WHERE id = %s FOR UPDATE", [challenge.id])
        challenge.invalidate_recordset()
        station = challenge.station_id
        token_payload = station._decode_token(challenge_token)
        if token_payload.get("challenge_uuid") != challenge.uuid or token_payload.get("ticket_id") != challenge.ticket_id.id:
            raise ValidationError(_("Capture challenge does not match the ticket."))
        if token_payload.get("user_id") != self.env.user.id or challenge.user_id != self.env.user:
            raise AccessError(_("Capture challenge belongs to another user."))
        now = fields.Datetime.now()
        if challenge.consumed_at:
            raise ValidationError(_("Capture challenge was already consumed."))
        if challenge.expires_at < now or token_payload.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
            raise ValidationError(_("Capture challenge expired."))
        signed_payload = dict(capture)
        signature = signed_payload.pop("signature", None)
        if not station._verify(signed_payload, signature):
            raise ValidationError(_("Invalid edge capture signature."))
        required_identity = {
            "protocol_version": "1", "station": station.code, "terminal_number": station.terminal_number,
            "scale_number": station.scale_number, "challenge_uuid": challenge.uuid,
        }
        if any(str(signed_payload.get(key)) != value for key, value in required_identity.items()):
            raise ValidationError(_("Edge capture identity does not match the challenge."))
        try:
            raw = base64.b64decode(signed_payload["raw_response"], validate=True)
        except (KeyError, ValueError, binascii.Error) as error:
            raise ValidationError(_("Malformed base64 IT3 response.")) from error
        parsed = parse_rn_frame(raw, station)
        comparisons = {
            "archive_id": parsed["archive_id"].strip(), "gross": parsed["gross_text"].strip(),
            "tare": parsed["tare_text"].strip(), "net": parsed["net_text"].strip(),
            "unit": parsed["unit"], "tare_code": parsed["tare_code"], "weighing_range": parsed["weighing_range"],
            "scale_status": parsed["scale_status"], "it3_crc16": parsed["crc"],
        }
        if any(str(signed_payload.get(key, "")).strip() != str(value).strip() for key, value in comparisons.items()):
            raise ValidationError(_("Signed capture fields do not match the raw IT3 response."))
        try:
            signed_terminal_dt = datetime.fromisoformat(signed_payload["terminal_timestamp"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValidationError(_("Malformed signed terminal timestamp.")) from error
        if signed_terminal_dt.replace(tzinfo=None) != parsed["terminal_datetime"]:
            raise ValidationError(_("Signed terminal timestamp does not match the raw IT3 response."))
        ticket = challenge.ticket_id
        if parsed["archive_id"].strip(" 0") == "" and (station.archive_mode == "asm" or ticket.commercial_role != "no_charge"):
            raise ValidationError(_("Archive ID zero is not valid for a commercial capture."))
        terminal_dt = parsed["terminal_datetime"]
        values = {
            "ticket_id": ticket.id, "station_id": station.id, "position": challenge.position,
            "protocol_version": signed_payload["protocol_version"], "capture_uuid": signed_payload["capture_uuid"],
            "challenge_uuid": challenge.uuid, "terminal_number": parsed["terminal_number"],
            "scale_number": parsed["scale_number"], "terminal_timestamp": terminal_dt,
            "terminal_date": terminal_dt.date(), "archive_mode": signed_payload.get("archive_mode", station.archive_mode),
            "archive_id": parsed["archive_id"].strip(), "gross_text": parsed["gross_text"].strip(),
            "tare_text": parsed["tare_text"].strip(), "net_text": parsed["net_text"].strip(),
            "gross_kg": parsed["gross_kg"], "tare_kg": parsed["tare_kg"], "net_kg": parsed["net_kg"],
            "unit": parsed["unit"], "tare_code": parsed["tare_code"], "weighing_range": parsed["weighing_range"],
            "scale_status": parsed["scale_status"], "it3_crc16": parsed["crc"], "raw_response": signed_payload["raw_response"],
            "edge_received_at": _edge_datetime(signed_payload["edge_received_at"]), "edge_signature": signature,
        }
        challenge.consumed_at = now
        measurement = self.env["weighbridge.measurement"].sudo().with_context(weighbridge_verified_capture=True).create(values)
        ticket._accept_measurement(measurement)
        return {"ticket_id": ticket.id, "ticket_state": ticket.state, "measurement_id": measurement.id}
