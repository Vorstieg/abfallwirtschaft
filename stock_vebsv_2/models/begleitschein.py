import logging
import os

from odoo import models, fields, _, api
from odoo.exceptions import UserError

from .library.auth import Auth
from .library.vebsv_begleitschein import VebsvBegleitscheinLine
from .library.mappings import *
from .library.message.begleitschein_message_service import VebsvBegleitschein
from .library.vebsv_service import VEBSVService

_logger = logging.getLogger(__name__)

COMPANY_GLN_MISSING = "You need to have a GLN configured for your company"


class Begleitschein(models.Model, VebsvBegleitschein):
    _name = "waste.begleitschein"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    self_is_main_organizer = fields.Boolean(string="Self is Main Organizer", default=True)

    stock_picking_id = fields.Many2one(
        'stock.picking', 'Stock Picking', index=True, ondelete='set null')

    name = fields.Char(string='Begleitschein Ref', required=True, copy=False)

    source_partner_id = fields.Many2one('res.partner', string='Source Partner', required=True, change_default=True,
                                        tracking=True)
    target_partner_id = fields.Many2one('res.partner', string='Target Partner', required=True, change_default=True,
                                        tracking=True)
    # When implementing drop-shipping with multiple partners, this needs to change to a many2many
    dropship_partner_id = fields.Many2one('res.partner', string='Dropship Partner')
    company_partner_id = fields.Many2one('res.partner', string="Company Partner", related='company_id.partner_id',
                                         store=True, readonly=True)
    transport_partner_id = fields.Many2one('res.partner', string="Transport Partner")
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
        ('confirmed', 'Confirmed'),
        ('in_transport', 'In transport'),
        ('transport_complete', 'Transport complete'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='Status', default='new', readonly=True)

    company_id = fields.Many2one('res.company', 'Company', required=True)

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
        source_partner_gln = self.source_partner_id.get_person_gln()
        target_partner_gln = self.target_partner_id.get_person_gln()

        sms_telephone_number = self.source_partner_id.sms_solution_phone_number if self.source_partner_id.enable_sms_solution else False

        if source_partner_gln == target_partner_gln:
            raise UserError(_("Handover and takeover party cannot be the same."))

        if len(self.begleitschein_lines) == 0:
            raise UserError(_("You need at least one product with a waste code"))
        if self.target_partner_id.enable_sms_solution and not sms_telephone_number:
            raise UserError(_("If the sms solution is active, the partner needs to have a phone number configured"))

        has_dangerous_waste = self._get_unified_service().start_begleitschein(self, sms_telephone_number)

        if not has_dangerous_waste:
            self.state = 'confirmed'

    def _get_shipment(self):
        shipment_items = [line.get_shipment_item(index + 1) for index, line in enumerate(self.begleitschein_lines)]
        return Shipment(self.shipment_uuid, self.name, shipment_items,
                        PlannedWaypoint(Period(datetime.now(), datetime.now()), "pickup_site", "handover"),
                        PlannedWaypoint(Period(datetime.now(), datetime.now()), "dropoff_site", "takeover"))

    def start_transport(self):
        if self.state != 'confirmed':
            raise UserError(_("You can only start transport for a confirmed begleitschein."))
        if not self.target_site.gtin:
            raise UserError(_("You need to define a target site."))
        if not self.source_site.gtin:
            raise UserError(_("You need to define a source site."))

        self._get_unified_service().start_transport(self, self.name)
        self.state = 'in_transport'

    def end_transport(self):
        if self.state != 'in_transport' and self.state != 'transport_complete':
            raise UserError(_("Can not finish a begleitschein, that is still in transport"))

        self._get_unified_service().end_transport(self)

        self.state = 'done'

    def cancel_begleitschein(self):
        self._get_begleitschein_message_service().cancel_begleitschein()

        self.state = 'canceled'

    def declare_begleitschein(self):
        if not self.source_site.gtin:
            raise UserError(_("You need to define a source site."))
        self._get_unified_service().declare_begleitschein(self)

        self.state = 'confirmed'

    def _get_unified_service(self):
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
        return VEBSVService(auth)


class BegleitscheinLine(models.Model, VebsvBegleitscheinLine):
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
            NetProperty("9008390104439", self.product_qty, "9008390100028")
        )

    def requires_reporting(self):
        return self.product_id.waste_type_id.dangerous or self.contains_pop
