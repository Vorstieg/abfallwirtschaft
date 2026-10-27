from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WeighbridgeMeasurement(models.Model):
    _name = "weighbridge.measurement"
    _description = "Immutable Certified Weighbridge Measurement"
    _order = "terminal_timestamp desc, id desc"
    _check_company_auto = True

    ticket_id = fields.Many2one("weighbridge.ticket", required=True, ondelete="restrict", index=True, check_company=True)
    company_id = fields.Many2one(related="ticket_id.company_id", store=True, index=True)
    station_id = fields.Many2one("weighbridge.station", required=True, ondelete="restrict", index=True, check_company=True)
    position = fields.Selection([("first", "First"), ("second", "Second")], required=True)
    protocol_version = fields.Char(required=True)
    capture_uuid = fields.Char(required=True, index=True)
    challenge_uuid = fields.Char(required=True, index=True)
    terminal_number = fields.Char(required=True)
    scale_number = fields.Char(required=True)
    terminal_timestamp = fields.Datetime(required=True, index=True)
    terminal_date = fields.Date(required=True, index=True)
    archive_mode = fields.Char(required=True)
    archive_id = fields.Char(required=True, index=True)
    gross_text = fields.Char(required=True)
    tare_text = fields.Char(required=True)
    net_text = fields.Char(required=True)
    gross_kg = fields.Float(required=True, digits=(16, 3))
    tare_kg = fields.Float(required=True, digits=(16, 3))
    net_kg = fields.Float(required=True, digits=(16, 3))
    unit = fields.Char(required=True)
    tare_code = fields.Char()
    weighing_range = fields.Char()
    scale_status = fields.Char(required=True)
    it3_crc16 = fields.Char(required=True)
    raw_response = fields.Binary(required=True, attachment=False, groups="abfall_weighbridge.group_weighbridge_station_admin")
    edge_received_at = fields.Datetime(required=True)
    edge_signature = fields.Char(required=True, groups="abfall_weighbridge.group_weighbridge_station_admin")

    _capture_uuid_uniq = models.Constraint("unique(capture_uuid)", "This edge capture was already committed.")
    _archive_record_uniq = models.Constraint(
        "unique(station_id, terminal_number, scale_number, terminal_date, archive_id)",
        "This certified archive record was already used.",
    )
    _ticket_position_uniq = models.Constraint("unique(ticket_id, position)", "This ticket already has this measurement.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("weighbridge_verified_capture"):
            raise UserError(_("Measurements can only be created through verified capture."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Certified measurements are immutable."))

    def unlink(self):
        raise UserError(_("Certified measurements cannot be deleted."))

