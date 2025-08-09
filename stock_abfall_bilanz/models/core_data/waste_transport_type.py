from odoo import models, fields, api

# Codeliste 9997
class WasteTransportType(models.Model):
    _name = "waste.transport.type"

    gtin = fields.Char('GTIN')
    name = fields.Char('Name')
    description = fields.Char('Description')
