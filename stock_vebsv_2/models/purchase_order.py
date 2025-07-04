from odoo import models, fields, api, _
from .library.auth import Auth
from .library.begleitschein_ws_transfer import request_waste_transfer_id
import os
import uuid

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def send_begleitschein(self):
        config_params = self.env['ir.config_parameter'].sudo()
        connector_id = os.getenv('CONNECTOR_ID')
        connector_key = os.getenv('CONNECTOR_KEY')

        auth = Auth(config_params.get_param('waste_management.edm_username'),
                    config_params.get_param('waste_management.edm_secret'),
                    connector_id,
                    connector_key)
        print(request_waste_transfer_id(auth, uuid.uuid4()))
