from odoo import models, fields, _
from odoo.exceptions import UserError
from ..utils.eras_client import ErasClient


class WasteTreatmentSite(models.Model):
    _name = "waste.treatment.site"
    _description = "Waste Treatment Site"

    gtin = fields.Char(string='Location GLN', help="Global Trade Item Number.")
    name = fields.Char(string='Site Name')
    partner_id = fields.Many2one('res.partner', string='Partner')
    treatment_installations = fields.One2many('waste.treatment.installation', "treatment_site_id", string='Treatment Installations')


class WasteTreatmentInstallation(models.Model):
    _name = "waste.treatment.installation"
    _description = "Waste Treatment Installation"

    gtin = fields.Char(string='Installation GLN', help="Global Trade Item Number.")
    name = fields.Char(string='Installation Name')
    treatment_site_id = fields.Many2one('waste.treatment.site', string='Location')
