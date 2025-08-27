import os
import uuid

from odoo import models, fields, _
from odoo.exceptions import UserError

from odoo.addons.stock_vebsv_2.models.library.message.begleitschein_ws_message import BegleitScheinMockMessageService
from .library.auth import Auth
from .library.structure import *

COMPANY_GLN_MISSING = "You need to have a GLN configured for your company"


class WasteBegleitschein(models.Model):
    _name = "waste.begleitschein"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    purchase_order_id = fields.Many2one(
        'purchase.order', 'Purchase Order', index=True, ondelete='set null')

    name = fields.Char(string='Begleitschein Ref', required=True, readonly=True, copy=False)

    partner_id = fields.Many2one('res.partner', string='Target', required=True, change_default=True, tracking=True)
    company_partner_id = fields.Many2one('res.partner', string='Company', required=True, change_default=True,
                                         tracking=True)

    source_installation = fields.Many2one('waste.treatment.installation', string='Source Installation', required=False)
    source_site = fields.Many2one('waste.treatment.site', string='Source Site')

    target_installation = fields.Many2one('waste.treatment.installation', string='Target Installation', required=False)
    target_site = fields.Many2one('waste.treatment.site', string='Target Site')

    begleitschein_lines = fields.One2many(
        comodel_name='waste.begleitschein.line',
        inverse_name='begleitschein_id',
        string="Begleitschein Lines",
        copy=True, auto_join=True)

    shipment_uuid = fields.Char('Shipment UUID', default=uuid.uuid4())
    business_case_uuid = fields.Char('Business Case UUID', default=uuid.uuid4())
    transport_uuid = fields.Char('Transport UUID', default=uuid.uuid4(), )

    state = fields.Selection([
        ('new', 'New'),
        ('in_transport', 'In Transport'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='Status', default='new')

    def start_begleitschein(self):
        partner_gln = self._get_person_gln(self.partner_id, _("Partner needs to have a GLN configured"))
        company_gln = self._get_person_gln(self.company_partner_id, _(COMPANY_GLN_MISSING))
        if len(self.begleitschein_lines) == 0:
            raise UserError(_("You need at least one product with a waste code"))

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
        ) for index, line in enumerate(self.begleitschein_lines)
        ]

        organizations = [Organisation(partner_gln, "handover"),
                         Organisation(company_gln, "takeover")]
        shipment = Shipment(self.shipment_uuid, self.name, shipment_items)

        planned_waypoints = [PlannedWaypoint(datetime.now(), datetime.now(), "pickup_site", "handover", True, False),
                             (datetime.now(), datetime.now(), "dropoff_site", "takeover", False, False)]

        transport_items = list(map(lambda line: TransportItem(line.product_id.waste_type_id.gtin, 'None',
                                                              False,
                                                              NetProperty("9008390104439", line.product_qty,
                                                                          "9008390100028")),
                                   self.begleitschein_lines))

        self._get_begleitschein_message_service().create_begleitschein(organizations, shipment, self, partner_gln,
                                                                       company_gln, planned_waypoints, transport_items,
                                                                       self.name)

    def start_transport(self):
        if self.state != 'new':
            raise UserError(_("You already started a transport."))

        transport_mean = TransportMean("Straße", "9008390100059")

        self._get_begleitschein_message_service().start_transport(transport_mean, self, "", "")

        self.state = 'in_transport'

    def end_transport(self):
        if self.state != 'in_transport':
            raise UserError(_("Can not finish a begleitschein, that is still in transport"))

        transport_mean = TransportMean("Straße", "9008390100059")
        self._get_begleitschein_message_service().end_transport(transport_mean, self, "", "", [], "")

        self.state = 'done'

    def cancel_begleitschein(self):
        self._get_begleitschein_message_service().cancel_begleitschein()

        self.state = 'canceled'

    def pull_changes(self):
        company_gln = self._get_person_gln(self.company_partner_id, _(COMPANY_GLN_MISSING))
        response = self._get_begleitschein_message_service().pull_news(company_gln)

    def _get_begleitschein_message_service(self):
        config_params = self.env['ir.config_parameter'].sudo()
        auth = Auth(config_params.get_param('waste_management.edm_username'),
                    config_params.get_param('waste_management.edm_secret'),
                    os.getenv('CONNECTOR_ID'),
                    os.getenv('CONNECTOR_KEY'),
                    config_params.get_param('waste_management.edm_db_uuid'))
        return BegleitScheinMockMessageService(auth)

    def _get_person_gln(self, contact, error):
        try:
            partner_gln = contact.id_numbers.display_name
        except AttributeError:
            raise UserError(error)
        return partner_gln


class WasteBegleitscheinLine(models.Model):
    _name = "waste.begleitschein.line"
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Product",
        change_default=True, ondelete='restrict', index='btree_not_null')

    product_qty = fields.Float(
        string="Quantity", default=1.0,
        store=True, readonly=False, required=True)

    begleitschein_id = fields.Many2one(
        'waste.begleitschein', 'Begleitschein', index=True, ondelete='set null')
