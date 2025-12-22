from odoo import models, fields

class WasteQuantificationType(models.Model):
    _name = "waste.quantification.type"
    _description = "Waste Quantification Type"

    gtin = fields.Char('GTIN')
    name = fields.Char('Name')
    code = fields.Char('Description')
