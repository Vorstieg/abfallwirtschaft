from odoo import models, fields, api

# Codeliste 9997
class WasteTransportType(models.Model):
    _name = "waste.transport.type"
    _description = "Waste Transport Type"

    gtin = fields.Char('GTIN')
    name = fields.Char('Name')
    description = fields.Char('Description')
