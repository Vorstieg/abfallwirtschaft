import logging
import os

from odoo import models, fields, _
from odoo.exceptions import UserError

from .library.auth import Auth
from .library.mappings import *
from .library.message.begleitschein_message_service import BegleitscheinMessageService

COMPANY_GLN_MISSING = "You need to have a GLN configured for your company"

_logger = logging.getLogger(__name__)


class Begleitschein(models.Model):
    _name = "waste.begleitschein"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    stock_picking_id = fields.Many2one(
        'stock.picking', 'Stock Picking', index=True, ondelete='set null')

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

        organizations = [Organisation(partner_gln, "handover"),
                         Organisation(company_gln, "takeover")]

        self._get_begleitschein_message_service().create_begleitschein(organizations, self._get_shipment(), self,
                                                                       partner_gln, company_gln)

    def _get_shipment(self):
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
        shipment = Shipment(self.shipment_uuid, self.name, shipment_items)
        return shipment

    def start_transport(self):
        if self.state != 'new':
            raise UserError(_("You already started a transport."))

        partner_gln = self._get_person_gln(self.partner_id, _("Partner needs to have a GLN configured"))
        company_gln = self._get_person_gln(self.company_partner_id, _(COMPANY_GLN_MISSING))
        transport_mean = TransportMean("Strasse", "9008390100059")
        organizations = [Organisation(partner_gln, "handover"),
                         Organisation(company_gln, "takeover")]
        planned_waypoints = [PlannedWaypoint(datetime.now(), datetime.now(), "pickup_site", "handover", True, False),
                             PlannedWaypoint(datetime.now(), datetime.now(), "dropoff_site", "takeover", False, False)]
        local_units = [LocalUnit("pickup_site", "9008390004500", "9008390109199"),
                       LocalUnit("dropoff_site", "9008390004494", "9008390109199")]


        self._get_begleitschein_message_service().start_transport(transport_mean, self, partner_gln, company_gln,
                                                                  organizations,local_units,self._get_shipment(), planned_waypoints,self.name)

        self.state = 'in_transport'

    def end_transport(self):
        if self.state != 'in_transport':
            raise UserError(_("Can not finish a begleitschein, that is still in transport"))

        partner_gln = self._get_person_gln(self.partner_id, _("Partner needs to have a GLN configured"))
        company_gln = self._get_person_gln(self.company_partner_id, _(COMPANY_GLN_MISSING))
        transport_mean = TransportMean("Strasse", "9008390100059")

        organizations = [Organisation(partner_gln, "handover"), Organisation(company_gln, "takeover")]

        self._get_begleitschein_message_service().end_transport(transport_mean, self, partner_gln, company_gln,
                                                                organizations,
                                                                self._get_shipment())

        self.state = 'done'

    def cancel_begleitschein(self):
        self._get_begleitschein_message_service().cancel_begleitschein()

        self.state = 'canceled'

    def pull_changes(self):
        config_params = self.env['ir.config_parameter'].sudo()
        edm_last_transaction_uuid = config_params.get_param(
            'waste_management.edm_last_transaction_uuid') or "00000000-0000-0000-0000-000000000000"

        company_gln = self._get_person_gln(self.company_partner_id, _(COMPANY_GLN_MISSING))
        respone = self._get_begleitschein_message_service().pull_news(company_gln, edm_last_transaction_uuid)
        for line in respone["changes"]:
            if line["state"] == 'NEW':
                begleitschein = line["begleitschein"]
                handover_partner = self.env["res.partner.id_number"].search(
                    [("name", "=", begleitschein["handover_gln"])])
                takeover_partner = self.env["res.partner.id_number"].search(
                    [("name", "=", begleitschein["takeover_gln"])])
                new_begleitschein = self.env['waste.begleitschein'].create({
                    'name': f"{takeover_partner.partner_id.name} {begleitschein['name']}",
                    'partner_id': takeover_partner.partner_id.id,
                    'company_partner_id': handover_partner.partner_id.id,
                    'business_case_uuid': begleitschein["business_case_uuid"],
                    'begleitschein_lines': [(0, 0, {
                        'product_qty': l["quantity"],
                        'contains_pop': l["pop"],
                        'abfallart': self.env['waste.type'].search([("gtin", "=", l["abfallart"])]).id,
                    }) for l in begleitschein["begleitschein_lines"]],
                })
                new_begleitschein.message_post(
                    body=line["message"],
                    subtype_xmlid='mail.mt_note'
                )
            elif line["state"] == 'INFO':
                for begleitschein in (self.env['waste.begleitschein']
                        .search([("business_case_uuid", "=", line["begleitschein"]["business_case_uuid"])])):
                    begleitschein.message_post(body=line["message"], subtype_xmlid='mail.mt_note')

        config_params.set_param('waste_management.edm_last_transaction_uuid', respone["last_transaction_uuid"])

    def _get_begleitschein_message_service(self):
        config_params = self.env['ir.config_parameter'].sudo()

        edm_username = config_params.get_param('waste_management.edm_username')
        edm_secret = config_params.get_param('waste_management.edm_secret')

        connector_id = os.getenv('CONNECTOR_ID')
        connector_key = os.getenv('CONNECTOR_KEY')

        if not edm_username or not edm_secret:
            raise UserError(_("You need to configure edm username and secret."))
        if not connector_id or not connector_key:
            raise UserError(_("You need to configure connector id and connector key."))

        auth = Auth(edm_username, edm_secret, connector_id, connector_key,
                    config_params.get_param('waste_management.edm_db_uuid'))
        return BegleitscheinMessageService(auth)

    def _get_person_gln(self, contact, error):
        try:
            partner_gln = contact.id_numbers.display_name
        except AttributeError:
            raise UserError(error)
        return partner_gln


class BegleitscheinLine(models.Model):
    _name = "waste.begleitschein.line"
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Product",
        change_default=True, ondelete='restrict', index='btree_not_null')

    abfallart = fields.Many2one('waste.type', "Abfallart")
    product_qty = fields.Float(string="Quantity", default=1.0, required=True)
    contains_pop = fields.Boolean(string="POP", default=False)

    begleitschein_id = fields.Many2one(
        'waste.begleitschein', 'Begleitschein', index=True, ondelete='set null')
