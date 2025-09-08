import logging
import os

from odoo import models, fields, _, api
from odoo.exceptions import UserError

from .library.transfer.begleitschein_transfer_service import BegleitscheinTransferService
from .library.auth import Auth
from .library.message.begleitschein_message_service import BegleitscheinMessageService
from .library.mappings import *

_logger = logging.getLogger(__name__)

COMPANY_GLN_MISSING = "You need to have a GLN configured for your company"

_logger = logging.getLogger(__name__)


class Begleitschein(models.Model):
    _name = "waste.begleitschein"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    stock_picking_id = fields.Many2one(
        'stock.picking', 'Stock Picking', index=True, ondelete='set null')

    purchase_order_id = fields.Many2one(
        'purchase.order', 'Purchase Order', index=True, ondelete='set null')

    name = fields.Char(string='Begleitschein Ref', required=True, copy=False)

    source_partner_id = fields.Many2one('res.partner', string='Target', required=True, change_default=True,
                                        tracking=True)
    target_partner_id = fields.Many2one('res.partner', string='Company', required=True, change_default=True,
                                        tracking=True)

    source_installation = fields.Many2one('waste.treatment.installation', string='Source Installation')
    source_site = fields.Many2one('waste.treatment.site', string='Source Site')

    target_installation = fields.Many2one('waste.treatment.installation', string='Target Installation')
    target_site = fields.Many2one('waste.treatment.site', string='Target Site')

    begleitschein_lines = fields.One2many(
        comodel_name='waste.begleitschein.line',
        inverse_name='begleitschein_id',
        string="Begleitschein Lines",
        copy=True, auto_join=True)

    shipment_uuid = fields.Char('Shipment UUID', default=lambda x: uuid.uuid4())
    business_case_uuid = fields.Char('Business Case UUID', default=lambda x: uuid.uuid4())
    transport_uuid = fields.Char('Transport UUID', default=lambda x: uuid.uuid4())

    state = fields.Selection([
        ('new', 'New'),
        ('in_transport', 'In Transport'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='Status', default='new', readonly=True)

    total_product_qty = fields.Float(
        string='Total Product Quantity',
        compute='_compute_total_product_qty',
        store=True,
    )

    @api.onchange('source_site')
    def _onchange_source_site(self):
        self.source_installation = False

    @api.onchange('target_site')
    def _onchange_target_site(self):
        self.target_installation = False

    @api.depends('begleitschein_lines.product_qty')
    def _compute_total_product_qty(self):
        for record in self:
            record.total_product_qty = sum(record.begleitschein_lines.mapped('product_qty'))

    def start_begleitschein(self):
        source_partner_gln = self._get_person_gln(self.source_partner_id, _("Partner needs to have a GLN configured"))
        target_partner_gln = self._get_person_gln(self.target_partner_id, _(COMPANY_GLN_MISSING))
        sms_telephone_number = self.source_partner_id.sms_solution_phone_number if self.source_partner_id.enable_sms_solution else False

        if source_partner_gln == target_partner_gln:
            raise UserError(_("Handover and takeover party cannot be the same."))

        if len(self.begleitschein_lines) == 0:
            raise UserError(_("You need at least one product with a waste code"))
        if self.target_partner_id.enable_sms_solution and not sms_telephone_number:
            raise UserError(_("If the sms solution is active, the partner needs to have a phone number configured"))

        for line in self.begleitschein_lines:
            if line.product_id.waste_type_id.dangerous:
                line.vebsv_id = self._get_begleitschein_transfer_service().request_vebsv_id()
        organizations = [Organisation(source_partner_gln, "handover"),
                         Organisation(target_partner_gln, "takeover")]
        local_units = [LocalUnit("pickup_site", self.source_site.gtin, "9008390109199"),
                       LocalUnit("dropoff_site", self.target_site.gtin, "9008390109199")]

        self._get_begleitschein_message_service().create_begleitschein(organizations, local_units, self._get_shipment(),
                                                                       self,
                                                                       source_partner_gln, target_partner_gln,
                                                                       sms_telephone_number)

    def _get_shipment(self):
        shipment_items = [line.get_shipment_item(index + 1) for index, line in enumerate(self.begleitschein_lines)]
        return Shipment(self.shipment_uuid, self.name, shipment_items,
                        PlannedWaypoint(Period(datetime.now(), datetime.now()), "pickup_site", "handover"),
                        PlannedWaypoint(Period(datetime.now(), datetime.now()), "dropoff_site", "takeover"))

    def start_transport(self):
        if self.state != 'new':
            raise UserError(_("You already started a transport."))
        if not self.target_site.gtin:
            raise UserError(_("You need to define a target site."))
        if not self.source_site.gtin:
            raise UserError(_("You need to define a source site."))

        partner_gln = self._get_person_gln(self.source_partner_id, _("Partner needs to have a GLN configured"))
        company_gln = self._get_person_gln(self.target_partner_id, _(COMPANY_GLN_MISSING))
        transport_mean = TransportMean("Strasse", "9008390100059")
        organizations = [Organisation(partner_gln, "handover"),
                         Organisation(company_gln, "takeover")]
        planned_waypoints = [
            PlannedWaypoint(Period(datetime.now(), datetime.now()), "pickup_site", "handover", True, False),
            PlannedWaypoint(Period(datetime.now(), datetime.now()), "dropoff_site", "takeover", False, False)]
        local_units = [LocalUnit("pickup_site", self.source_site.gtin, "9008390109199"),
                       LocalUnit("dropoff_site", self.target_site.gtin, "9008390109199")]

        self._get_begleitschein_message_service().start_transport(transport_mean, self, partner_gln, company_gln,
                                                                  organizations, local_units, self._get_shipment(),
                                                                  planned_waypoints, self.name)

        for begleitschein_line in self.begleitschein_lines:
            if begleitschein_line.product_id.waste_type_id.dangerous:
                self._get_begleitschein_transfer_service().declare_transport(
                    organizations,
                    local_units,
                    begleitschein_line.get_shipment_item(),
                    begleitschein_line.vebsv_id,
                    self.transport_uuid,
                    transport_mean,
                    planned_waypoints)

        self.state = 'in_transport'

    def end_transport(self):
        if self.state != 'in_transport':
            raise UserError(_("Can not finish a begleitschein, that is still in transport"))

        partner_gln = self._get_person_gln(self.source_partner_id, _("Partner needs to have a GLN configured"))
        company_gln = self._get_person_gln(self.target_partner_id, _(COMPANY_GLN_MISSING))
        transport_mean = TransportMean("Strasse", "9008390100059")

        organizations = [Organisation(partner_gln, "handover"), Organisation(company_gln, "takeover")]

        self._get_begleitschein_message_service().end_transport(self, partner_gln, company_gln,
                                                                self._get_shipment())

        local_units = [LocalUnit("dropoff_site", "9008390004494", "9008390109199")]
        for begleitschein_line in self.begleitschein_lines:
            if begleitschein_line.product_id.waste_type_id.dangerous:
                self._get_begleitschein_transfer_service().declare_takeover(
                    organizations,
                    local_units,
                    begleitschein_line.get_shipment_item(),
                    begleitschein_line.vebsv_id)

        self.state = 'done'

    def cancel_begleitschein(self):
        self._get_begleitschein_message_service().cancel_begleitschein()

        self.state = 'canceled'

    def pull_changes(self):
        config_params = self.env['ir.config_parameter'].sudo()
        edm_last_transaction_uuid = config_params.get_param(
            'waste_management.edm_last_transaction_uuid') or "00000000-0000-0000-0000-000000000000"

        company_gln = self._get_person_gln(self.target_partner_id, _(COMPANY_GLN_MISSING))
        respone = self._get_begleitschein_message_service().pull_news(company_gln, edm_last_transaction_uuid)
        for line in respone["changes"]:
            if line["state"] == 'NEW':
                begleitschein = line["begleitschein"]
                handover_partner = self.env["res.partner.id_number"].search(
                    [("name", "=", begleitschein["handover_gln"])])
                takeover_partner = self.env["res.partner.id_number"].search(
                    [("name", "=", begleitschein["takeover_gln"])])
                sanitised_partner_name = takeover_partner.partner_id.name.replace('\\', '').replace('/', '').replace(
                    ' ', '_')
                new_begleitschein = self.env['waste.begleitschein'].create({
                    'name': f"{sanitised_partner_name}_{begleitschein['name']}",
                    'source_partner_id': takeover_partner.partner_id.id,
                    'target_partner_id': handover_partner.partner_id.id,
                    'business_case_uuid': begleitschein["business_case_uuid"],
                    'begleitschein_lines': [(0, 0, {
                        'product_qty': l["quantity"],
                        'contains_pop': l["pop"],
                        'vebsv_id': l["vebsv_id"],
                        'abfallart': self.env['waste.type'].search([("gtin", "=", l["abfallart"])]).id,
                    }) for l in begleitschein["begleitschein_lines"]],
                })
                new_begleitschein.message_post(
                    body=line["message"],
                    subtype_xmlid='mail.mt_note'
                )
                # TODO will be handled by follow-up ticket
                local_units = [LocalUnit("pickup_site", "9008390004494", "9008390109199")]
                partner_gln = self._get_person_gln(new_begleitschein.source_partner_id,
                                                   _("Partner needs to have a GLN configured"))
                company_gln = self._get_person_gln(new_begleitschein.target_partner_id, _(COMPANY_GLN_MISSING))
                organisations = [Organisation(company_gln, "handover"),
                                 Organisation(partner_gln, "takeover")]

                for begleitschein_line in new_begleitschein.begleitschein_lines:
                    if begleitschein_line.abfallart.dangerous:
                        self._get_begleitschein_transfer_service().declare_begleitschein(
                            organisations,
                            local_units,
                            begleitschein_line.get_shipment_item(),
                            begleitschein_line.vebsv_id)
            elif line["state"] == 'INFO':
                for begleitschein in (self.env['waste.begleitschein']
                        .search([("business_case_uuid", "=", line["begleitschein"]["business_case_uuid"])])):
                    begleitschein.message_post(body=line["message"], subtype_xmlid='mail.mt_note')

        config_params.set_param('waste_management.edm_last_transaction_uuid', respone["last_transaction_uuid"])

    def _get_begleitschein_transfer_service(self):
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
        return BegleitscheinTransferService(auth)

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

    vebsv_id = fields.Char(
        string="VEBSV ID", store=True, readonly=False, required=False)

    def get_shipment_item(self, line_item_number=0):
        return ShipmentItem(
            uuid.uuid4(),
            line_item_number,
            self.abfallart.gtin,
            'None',
            self.abfallart.name,
            self.vebsv_id,
            False,
            NetProperty("9008390104439",
                        self.product_qty,
                        "9008390100028"
                        )
        )
