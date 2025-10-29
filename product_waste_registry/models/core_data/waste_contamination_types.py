from odoo import models, fields

#7835: Kontaminationsgruppen
class WasteContaminationType(models.Model):
    _name = "waste.contamination.type"

    gtin = fields.Char('GTIN')
    name = fields.Char('Name')
