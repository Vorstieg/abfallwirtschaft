from datetime import date

from odoo import http
from odoo.http import request, content_disposition

from .library.parser import create_waste_handling_notification_xml


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
