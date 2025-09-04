from odoo import models, fields


class WasteTreatmentSite(models.Model):
    _name = "waste.treatment.site"

    gtin = fields.Char(string='Location GLN', help="Global Trade Item Number.")
    name = fields.Char(string='Site Name')
    partner_id = fields.Many2one('res.partner', string='Partner')
    treatment_installations = fields.One2many('waste.treatment.installation', "treatment_site_id", string='Treatment Installations')


class WasteTreatmentInstallation(models.Model):
    _name = "waste.treatment.installation"

    gtin = fields.Char(string='Installation GLN', help="Global Trade Item Number.")
    name = fields.Char(string='Installation Name')
    treatment_site_id = fields.Many2one('waste.treatment.site', string='Location')
