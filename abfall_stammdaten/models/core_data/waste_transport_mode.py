from odoo import models, fields

class WasteTransportMode(models.Model):
    _name = "waste.transport.mode"
    _description = "Waste Transport Mode (Codeliste 2939)"

    name = fields.Char('Name', required=True)
    gtin = fields.Char('GTIN', required=True)
