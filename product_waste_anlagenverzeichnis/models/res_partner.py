# -*- coding: utf-8 -*-
from odoo import api, fields, models


class Partner(models.Model):
    _inherit = 'res.partner'

    waste_treatment_sites = fields.One2many(
        comodel_name='waste.treatment.site',
        inverse_name='partner_id', string='Waste Treatment Sites',)