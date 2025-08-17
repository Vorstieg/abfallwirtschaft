import os
import uuid

from odoo import models, fields, _
from odoo.exceptions import UserError

from odoo.addons.stock_vebsv_2.models.library.message.begleitschein_ws_message import BegleitScheinMockMessageService
from .library.auth import Auth
from .library.message.structure import *


class WasteBegleitschein(models.Model):
    _name = "waste.begleitschein"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    purchase_order_id = fields.Many2one(
        'purchase.order', 'Purchase Order', index=True, ondelete='set null')

    shipment_uuid = fields.Char('Shipment UUID', default=uuid.uuid4())
    business_case_uuid = fields.Char('Business Case UUID', default=uuid.uuid4())
    transport_uuid = fields.Char('Transport UUID', default=uuid.uuid4(),)

    state = fields.Selection([
        ('new', 'New'),
        ('in_transport', 'In Transport'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='Status', default='new')


    def start_transport(self):
        if self.state != 'new':
            raise UserError(_("You already started a transport."))

        config_params = self.env['ir.config_parameter'].sudo()
        auth = Auth(config_params.get_param('waste_management.edm_username'),
                    config_params.get_param('waste_management.edm_secret'),
                    os.getenv('CONNECTOR_ID'),
                    os.getenv('CONNECTOR_KEY'))
        begleitschein_message_service = BegleitScheinMockMessageService(auth)

        transport_mean = TransportMean("Straße","9008390100059")

        begleitschein_message_service.start_transport(transport_mean, self, "","")

        self.state = 'in_transport'

    def end_transport(self):
        if self.state != 'in_transport':
            raise UserError(_("Can not finish a begleitschein, that is still in transport"))

        config_params = self.env['ir.config_parameter'].sudo()
        auth = Auth(config_params.get_param('waste_management.edm_username'),
                    config_params.get_param('waste_management.edm_secret'),
                    os.getenv('CONNECTOR_ID'),
                    os.getenv('CONNECTOR_KEY'))
        begleitschein_message_service = BegleitScheinMockMessageService(auth)

        transport_mean = TransportMean("Straße","9008390100059")

        begleitschein_message_service.end_transport(transport_mean, self,"","",[],"")

        self.state = 'done'

    def cancel_begleitschein(self):
        config_params = self.env['ir.config_parameter'].sudo()
        auth = Auth(config_params.get_param('waste_management.edm_username'),
                    config_params.get_param('waste_management.edm_secret'),
                    os.getenv('CONNECTOR_ID'),
                    os.getenv('CONNECTOR_KEY'))
        begleitschein_message_service = BegleitScheinMockMessageService(auth)

        begleitschein_message_service.cancel_begleitschein()

        self.state = 'canceled'