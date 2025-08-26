from datetime import datetime
import json
import base64

import pytz
from odoo import http
from odoo.http import request, content_disposition

from odoo.addons.pos_registrierkasse.models.utils.a_trust_library import OrderData

from odoo.addons.pos_registrierkasse.models.utils.order_utils import jws_signature_compact

from .library.parser import create_waste_handling_notification_xml
from datetime import date

class DatenErfassungsProtokollController(http.Controller):

    @http.route('/download/abfallwirtschaft/<int:year>', type='http', auth='user')
    def download_your_file(self, year, **kwargs):
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        moves = request.env['waste.move'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])

        data = create_waste_handling_notification_xml(
            notification_type_code="JAB",
            obligated_party_id="AT1234567890123",
            period_start_date=date(year, 1, 1),
            period_end_date=date(year, 12, 31),
            waste_movements={}
        )

        # Send file as response
        return request.make_response(
            data,
            headers=[
                ('Content-Type', 'application/xml'),
                ('Content-Disposition', content_disposition(f"Abfallbilanz_{year}.xml"))
            ]
        )
