import base64
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlparse

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def b64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def b64url_decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class WeighbridgeStation(models.Model):
    _name = "weighbridge.station"
    _description = "Weighbridge Station"
    _inherit = ["mail.thread"]
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, copy=False)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    edge_url = fields.Char(required=True, help="HTTPS URL of the station-local edge service")
    allowed_origin = fields.Char(help="Exact Odoo browser origin accepted by the edge service")
    terminal_number = fields.Char(required=True, size=3, default="001")
    scale_number = fields.Char(required=True, size=1, default="1")
    protocol = fields.Selection([("tcp", "TCP"), ("serial", "Serial")], required=True, default="tcp")
    archive_mode = fields.Selection([("asm", "ASM required"), ("none", "No archive (non-commercial only)")], required=True, default="asm")
    terminal_date_format = fields.Char(required=True, default="%d.%m.%y")
    terminal_time_format = fields.Char(required=True, default="%H:%M")
    archive_id_length = fields.Selection([("4", "4 digits (Date + ID)"), ("6", "6 digit consecutive")], required=True, default="4")
    decimal_separator = fields.Selection([(".", "Dot"), (",", "Comma")], required=True, default=".")
    shared_secret = fields.Char(required=True, copy=False, groups="abfall_weighbridge.group_weighbridge_station_admin")
    connection_state = fields.Selection([("unknown", "Unknown"), ("connected", "Connected"), ("disconnected", "Disconnected"), ("stale", "Stale")], default="unknown", readonly=True)
    last_seen = fields.Datetime(readonly=True)
    sequence_id = fields.Many2one("ir.sequence", readonly=True, copy=False)

    _code_company_uniq = models.Constraint("unique(code, company_id)", "Station code must be unique per company.")

    @api.constrains("edge_url")
    def _check_edge_url(self):
        for station in self:
            parsed = urlparse(station.edge_url or "")
            if parsed.scheme == "https":
                continue
            if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                continue
            raise ValidationError(_("The edge service URL must use HTTPS, except for a loopback-only local development service."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for station in records.filtered(lambda s: not s.sequence_id):
            sequence = self.env["ir.sequence"].sudo().create({
                "name": _("Weighbridge Tickets - %s", station.name),
                "code": "weighbridge.ticket.%s" % station.id,
                "prefix": "%s/%%(year)s/" % station.code,
                "padding": 5,
                "company_id": station.company_id.id,
            })
            station.sequence_id = sequence
        return records

    def action_rotate_secret(self):
        self.ensure_one()
        self.shared_secret = secrets.token_urlsafe(48)
        self.message_post(body=_("Station signing secret rotated by %s.", self.env.user.display_name))

    def _sign(self, payload):
        self.ensure_one()
        return hmac.new(self.sudo().shared_secret.encode(), canonical_json(payload), hashlib.sha256).hexdigest()

    def _verify(self, payload, signature):
        self.ensure_one()
        expected = self._sign(payload)
        return hmac.compare_digest(expected, signature or "")

    def _issue_token(self, payload):
        self.ensure_one()
        encoded = b64url_encode(canonical_json(payload))
        signature = hmac.new(self.sudo().shared_secret.encode(), encoded.encode(), hashlib.sha256).digest()
        return "%s.%s" % (encoded, b64url_encode(signature))

    def _decode_token(self, token):
        self.ensure_one()
        try:
            encoded, supplied = token.split(".", 1)
            expected = hmac.new(self.sudo().shared_secret.encode(), encoded.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, b64url_decode(supplied)):
                raise ValueError
            return json.loads(b64url_decode(encoded))
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            raise ValidationError(_("Invalid capture challenge signature.")) from error
