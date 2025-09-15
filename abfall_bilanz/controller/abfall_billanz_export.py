from datetime import date

from odoo import http
from odoo.http import request, content_disposition
from odoo.exceptions import UserError

from .library.parser import create_waste_handling_notification_xml, WasteMovementLocation, Party, SpecifiedLocation, \
    WasteMovementSite, WasteHandlingNotification


class DatenErfassungsProtokollController(http.Controller):

    @http.route('/download/abfallwirtschaft/<int:year>', type='http', auth='user')
    def download_your_file(self, year, **kwargs):
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        moves = request.env['waste.move'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', '=', 'approved'),
        ])

        data = create_waste_handling_notification_xml(start_date, end_date, "AT123456789",
                                                      list(map(lambda x: self.map_move(x), moves)))

        # Send file as response
        return request.make_response(
            data,
            headers=[
                ('Content-Type', 'application/xml'),
                ('Content-Disposition', content_disposition(f"Abfallbilanz_{year}.xml"))
            ]
        )

    def map_move(self, move):
        origin_partner = move.origin_partner
        recipient_partner = move.recipient_partner
        handover_party = WasteMovementLocation(Party(origin_partner.get_person_gln(), origin_partner.name),
                                               SpecifiedLocation(
                                                   WasteMovementSite(move.origin_site.gtin,
                                                                     move.origin_site.name) if move.origin_site else None,
                                                   WasteMovementSite(move.origin_installation.gtin,
                                                                     move.origin_installation.name) if move.origin_installation else None),
                                               "9008390008393")
        takeover_party = WasteMovementLocation(Party(recipient_partner.get_person_gln(), recipient_partner.name),
                                               SpecifiedLocation(
                                                   WasteMovementSite(move.recipient_site.gtin,
                                                                     move.recipient_site.name) if move.recipient_site else None,
                                                   WasteMovementSite(move.recipient_installation.gtin,
                                                                     move.recipient_installation.name) if move.recipient_installation else None),
                                               "9008390008393")
        return WasteHandlingNotification(move.name, "9008390101643", handover_party, takeover_party,
                                         move.abfallart.gtin, "9008390100004", move.amount)
