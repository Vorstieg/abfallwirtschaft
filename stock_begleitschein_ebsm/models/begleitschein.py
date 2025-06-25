import io
from datetime import datetime
import base64

from odoo import models, fields, api, _

from .begleitschein_api import create_consignment


class AnvBegleitschein(models.Model):
    _inherit = 'stock.picking'  # Inherit from stock.picking
    _description = 'Begleitschein für gefährlichen Abfall'

    def send_begleitschein(self):
        move = self.move_ids[0]

        your_consignment_data = {
            'ConsignmentNumber': 'YOUR_CONSIGNMENT_NUMBER_XYZ',
            'ConsignmentDate': datetime.strftime(self.scheduled_date, "%d%m%y"),
            'SenderParty': {
                'PartyIdentifier': {'GLN': self.company_id.partner_id.id_numbers.display_name},
                'Name': self.company_id.partner_id.complete_name,
                # Add other SenderParty details as per XSD
            },
            'RecipientParty': {
                'PartyIdentifier': {'GLN': self.partner_id.id_numbers.display_name},
                'Name': self.company_id.partner_id.complete_name,
                # Add other RecipientParty details as per XSD
            },
            'WasteDetails': {
                'WasteCode': move.product_id.waste_type_id.key_number,
                'Quantity': {
                    'Value': move.product_qty,
                    'Unit': 'kg'
                },
                # Add other WasteDetails as per XSD
            },
        }
        create_consignment(self.company_id.partner_id.id_numbers.display_name, consignment_data=your_consignment_data)
