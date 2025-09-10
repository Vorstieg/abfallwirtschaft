from odoo import models, fields, api

# Codeliste 7521
class WasteRevocationReason(models.Model):
    _name = "waste.revocation.reason"

    gtin = fields.Char('GTIN')
    name = fields.Char('Name')
    description = fields.Char('Description')
