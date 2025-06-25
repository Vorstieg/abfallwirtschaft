import io
from datetime import datetime
import base64

from odoo import models, fields, api, _

from .begleitschein_api import create_consignment


class AnvBegleitschein(models.Model):
    _inherit = 'stock.picking'
    _description = 'Begleitschein für gefährlichen Abfall'

    def print_begleitschein(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/download/begleitschein/{self.id}',
            'target': 'self',
        }