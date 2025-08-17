import os
import uuid
from datetime import datetime

from odoo import models, fields, _
from odoo.exceptions import UserError

from .library.auth import Auth
from .library.message.begleitschein_ws_message import Organisation, Shipment, \
    ShipmentItem, \
    NetProperty, PlannedWaypoint, TransportItem, BegleitScheinMockMessageService


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    begleitscheine = fields.One2many('waste.begleitschein', 'purchase_order_id', string='Begleitscheine',
                                     copy=False, )

    def send_begleitschein(self):
        config_params = self.env['ir.config_parameter'].sudo()
        auth = Auth(config_params.get_param('waste_management.edm_username'),
                    config_params.get_param('waste_management.edm_secret'),
                    os.getenv('CONNECTOR_ID'),
                    os.getenv('CONNECTOR_KEY'))
        begleitScheinMessageService = BegleitScheinMockMessageService(auth)

        partner_gln = self._get_person_gln(self.partner_id, _("Partner needs to have a GLN configured"))
        company_gln = self._get_person_gln(self.company_id.partner_id,
                                           _("You need to have a GLN configured for your company"))

        waste_products = self.order_line.filtered(
            lambda l: l.product_id.waste_type_id
        )

        belgeitschein = self.env['waste.begleitschein'].create({
            'purchase_order_id': self.id
        })

        shipment_items = [ShipmentItem(
            uuid.uuid4(),
            index + 1,
            line.product_id.waste_type_id.gtin,
            'None',
            line.product_id.waste_type_id.name,
            False,
            NetProperty("9008390104439",
                        line.product_qty,
                        "9008390100028"
                        )
        ) for index, line in enumerate(waste_products)
        ]

        if len(shipment_items) == 0:
            raise UserError(_("You need at least one product with a waste code"))

        organizations = [Organisation(partner_gln, "handover"),
                         Organisation(company_gln, "takeover")]
        shipment = Shipment(belgeitschein.shipment_uuid, self.name, shipment_items)

        planned_waypoints = [PlannedWaypoint(datetime.now(), datetime.now(), "pickup_site", "handover", True, False),
                             (datetime.now(), datetime.now(), "dropoff_site", "takeover", False, False)]

        transport_items = list(map(lambda line: TransportItem(line.product_id.waste_type_id.gtin, 'None',
                                                              False,
                                                              NetProperty("9008390104439", line.product_qty,
                                                                          "9008390100028")),
                                   waste_products))

        begleitScheinMessageService.create_begleitschein(organizations, shipment, belgeitschein, partner_gln,
                                                         company_gln, planned_waypoints, transport_items, self.name)

    def _get_person_gln(self, contact, error):
        try:
            partner_gln = contact.id_numbers.display_name
        except AttributeError:
            raise UserError(error)
        return partner_gln

    def action_view_begleitscheine(self):
        self.ensure_one()
        action = self.env.ref('stock_vebsv_2.action_waste_begleitschein').read()[0]

        begleitschein_count = len(self.begleitscheine)
        if begleitschein_count > 1:
            action['domain'] = [('id', 'in', self.begleitscheine.ids)]
        elif begleitschein_count == 1:
            res = self.env.ref('stock_vebsv_2.view_waste_begleitschein_form', False)
            action['views'] = [(res and res.id or False, 'form')]
            action['res_id'] = self.begleitscheine.id
        else:
            action['domain'] = [('purchase_order_id', '=', self.id)]

        return action
