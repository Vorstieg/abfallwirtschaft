# -*- coding: utf-8 -*-
from odoo import api, fields, models


class BegleitscheinModal(models.TransientModel):
    _name = 'begleitschein.modal'
    _description = 'Start Begleitschein Modal'

    stock_picking_id = fields.Many2one(
        'stock.picking', 'Stock Picking', index=True, ondelete='set null')
    source_partner_id = fields.Many2one('res.partner', string='Source Partner', required=True,)
    target_partner_id = fields.Many2one('res.partner', string='Target Partner', required=True,)

    source_site = fields.Many2one('waste.treatment.site', string='Source Installation', required=True)
    target_site = fields.Many2one('waste.treatment.site', string='Target Installation', required=True)

    def create_begleitschein_action(self):
        self.stock_picking_id.create_begleitschein(self.source_site, self.target_site)