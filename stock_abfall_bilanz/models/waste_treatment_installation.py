from odoo import models, fields

class WasteTreatmentInstallation(models.Model):
    _name = "waste.treatment.installation"

    gtin = fields.Char(string='GTIN', help="Global Trade Item Number.")
    installation_name = fields.Char(string='Installation Name')
    location = fields.Many2one('waste.treatment.site', string='Location')

class WasteTreatmentSite(models.Model):
    _name = "waste.treatment.site"

    gtin = fields.Char(string='GTIN', help="Global Trade Item Number.")
    name = fields.Char(string='Site Name')
