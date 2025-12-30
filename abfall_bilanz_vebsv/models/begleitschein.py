# -*- coding: utf-8 -*-
from datetime import datetime
from operator import index

from odoo import api, fields, models

from odoo.addons.abfall_vebsv_2.models.library.vebsv_begleitschein import VebsvBegleitschein


class Begleitschein(models.Model, VebsvBegleitschein):
    _inherit = 'waste.begleitschein'

    def end_transport(self):
        val = super().end_transport()
        moves = [
            {
                'name': f"{self.name} {index}",
                'recipient_partner': self.target_partner_id.id,
                'origin_partner': self.source_partner_id.id,
                'recipient_installation': self.target_installation.id,
                'origin_installation': self.source_installation.id,
                'recipient_site': self.source_site.id,
                'origin_site': self.target_site.id,
                'abfallart': line.abfallart.id,
                'amount': line.product_qty,
                'date': datetime.today(),
                'state': 'approved',
            } for index, line in enumerate(self.begleitschein_lines)]

        self.env['waste.move'].create(moves)

        return val