from odoo import models, fields

class WasteReclassificationReason(models.Model):
    _name = "waste.reclassification.reason"
    _description = "Waste Reclassification Reason (Codeliste 3327)"

    name = fields.Char(string='Name', required=True)
    gtin = fields.Char(string='GTIN', required=True)
    description = fields.Text(string='Description')
