import logging
import os
import uuid

from odoo import models, fields, _, api
from odoo.exceptions import UserError

from .library.auth import Auth
from .library.mappings import *
from .library.message.begleitschein_message_service import VebsvBegleitschein
from .library.vebsv_begleitschein import VebsvBegleitscheinLine, MessageRequestType, TransferRequestType
from .library.vebsv_service import VEBSVService

_logger = logging.getLogger(__name__)

COMPANY_GLN_MISSING = "You need to have a GLN configured for your company"

class Begleitschein(models.Model, VebsvBegleitschein):
    _name = "waste.begleitschein"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    stock_picking_id = fields.Many2one(
        'stock.picking', 'Stock Picking', index=True, ondelete='set null')

    name = fields.Char(string='Begleitschein Ref', required=True, copy=False)

    source_partner_id = fields.Many2one('res.partner', string='Source Partner', required=True, change_default=True,
                                        tracking=True)
    target_partner_id = fields.Many2one('res.partner', string='Target Partner', required=True, change_default=True,
                                        tracking=True)
    organizing_partner_id = fields.Many2one('res.partner', string='Organizing Partner')
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
        copy=True, auto_join=False)

    request_identifiers = fields.One2many(
        comodel_name='waste.begleitschein.request.identifier',
        inverse_name='begleitschein_id',
        string="Begleitschein Request Identifiers",
        copy=False, auto_join=False)

    shipment_uuid = fields.Char('Shipment UUID', default=lambda x: uuid.uuid4())
    business_case_uuid = fields.Char('Business Case UUID', default=lambda x: uuid.uuid4())
    transport_uuid = fields.Char('Transport UUID', default=lambda x: uuid.uuid4())

    state = fields.Selection([
        ('0_draft', 'Draft'),
        ('1_declared', 'Declared'),
        ('2_confirmed', 'Confirmed'),
        ('4_in_transport', 'In Transport'),
        ('6_transport_complete', 'Transport complete'),
        ('8_done', 'Done'),
        ('9_canceled', 'Canceled'),
    ], string='Status', default='0_draft', readonly=True)

    company_id = fields.Many2one('res.company', 'Company', required=True)

    total_product_qty = fields.Float(
        string='Total Product Quantity',
        compute='_compute_total_product_qty',
        store=True,
    )
    self_is_main_organizer = fields.Boolean(string="Self is Main Organizer", compute='_compute_self_is_main_organizer',
                                            store=True)

    is_cancel_button_visible = fields.Boolean(string="Cancel Button is visible",
                                              compute='_compute_is_cancel_button_visible',
                                              store=True)

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

    @api.depends('organizing_partner_id', 'company_partner_id')
    def _compute_self_is_main_organizer(self):
        for record in self:
            record.self_is_main_organizer = record.organizing_partner_id == record.company_partner_id

    @api.depends('organizing_partner_id', 'company_partner_id', 'state')
    def _compute_is_cancel_button_visible(self):
        for record in self:
            match record.state:
                case "0_draft":
                    record.is_cancel_button_visible = False
                case "1_declared":
                    record.is_cancel_button_visible = record.organizing_partner_id == record.company_partner_id
                case "2_confirmed":
                    record.is_cancel_button_visible = record.company_partner_id.is_source(record)
                case "4_in_transport":
                    record.is_cancel_button_visible = (record.organizing_partner_id == record.company_partner_id
                                                       or record.company_partner_id.is_carrier(record))
                case "6_transport_complete":
                    record.is_cancel_button_visible = (record.organizing_partner_id == record.company_partner_id
                                                       or record.company_partner_id.is_carrier(record))
                case "8_done":
                    record.is_cancel_button_visible = (record.company_partner_id.is_target(record)
                                                       or record.company_partner_id.is_carrier(record))
                case "9_canceled":
                    record.is_cancel_button_visible = record.organizing_partner_id == record.company_partner_id

    @api.model_create_multi
    def create(self, vals_list):
        for value in vals_list:
            if not value.get("company_id"):
                value["company_id"] = self.env.user.company_id.id
            if not value.get("organizing_partner_id"):
                value["organizing_partner_id"] = self.env.user.company_id.partner_id.id
            if not value.get("transport_partner_id"):
                value["transport_partner_id"] = self.env.user.company_id.partner_id.id

        return super().create(vals_list)

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

        has_dangerous_waste = self._get_unified_service().start_begleitschein(self, self.company_partner_id,
                                                                              sms_telephone_number)

        if not has_dangerous_waste:
            self.state = '2_confirmed'
        else:
            self.state = '1_declared'

    def confirm_begleitschein(self):
        if not self.source_site.gtin:
            raise UserError(_("You need to define a source site."))
        self._get_unified_service().confirm_begleitschein(self)

        self.state = '2_confirmed'

    def start_transport(self):
        if self.state != '2_confirmed':
            raise UserError(_("You can only start transport for a confirmed begleitschein."))
        if not self.target_site.gtin:
            raise UserError(_("You need to define a target site."))
        if not self.source_site.gtin:
            raise UserError(_("You need to define a source site."))

        self._get_unified_service().start_transport(self, self.company_partner_id, self.name)
        self.state = '4_in_transport'

    def end_transport(self):
        if self.state != '4_in_transport' and self.state != '6_transport_complete':
            raise UserError(_("Can not finish a begleitschein, that is still in transport"))

        self._get_unified_service().end_transport(self, self.company_partner_id)

        self.state = '8_done'

    def cancel_begleitschein(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cancel Begleitschein'),
            'res_model': 'begleitschein.cancel.wizard',
            'target': 'new',
            'view_mode': 'form',
            'context': {
                'default_begleitschein_id': self.id,
                'default_cancel_state': self.state,
            },
        }

    def action_cancel(self, revocation_reason):
        self.ensure_one()
        service = self._get_unified_service()

        if self.state == '1_declared':
            service.cancel_declared(self, self.company_partner_id, revocation_reason)
            self.write({
                'state': '0_draft',
                'shipment_uuid': str(uuid.uuid4()),
                'business_case_uuid': str(uuid.uuid4()),
                'transport_uuid': str(uuid.uuid4()),
            })
        elif self.state == '2_confirmed':
            service.cancel_confirmed(self, revocation_reason)
            self.state = '1_declared'
        elif self.state == '4_in_transport':
            service.cancel_in_transport(self, self.company_partner_id, revocation_reason)
            self.write({
                'state': '2_confirmed',
                'transport_uuid': str(uuid.uuid4())
            })
        elif self.state == '8_done':
            service.cancel_done(self, self.company_partner_id, revocation_reason)
            self.state = '4_in_transport'

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

    def get_shipment(self):
        shipment_items = [line.get_shipment_item(index + 1) for index, line in enumerate(self.begleitschein_lines)]
        return Shipment(self.shipment_uuid, self.name, shipment_items,
                        PlannedWaypoint(Period(datetime.now(), datetime.now()), "pickup_site", "handover"),
                        PlannedWaypoint(Period(datetime.now(), datetime.now()), "dropoff_site", "takeover"))

    def get_request_identifier(self, message_request_type: MessageRequestType, suffix: str = ""):
        return self.request_identifiers.filtered(lambda r: r.name == (message_request_type.name + suffix)).uuid

    def add_request_identifier(self, message_request_type: MessageRequestType, suffix: str, uuid: str):
        name = message_request_type.name + suffix
        existing = self.request_identifiers.filtered(lambda r: r.name == name)
        if existing:
            existing.write({'uuid': uuid})
        else:
            self.write({'request_identifiers': [(0, 0, {'name': name, 'uuid': uuid})]})


class BegleitscheinLine(models.Model, VebsvBegleitscheinLine):
    _name = "waste.begleitschein.line"
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Product",
        change_default=True, ondelete='restrict', index='btree_not_null')

    abfallart = fields.Many2one('waste.type', "Abfallart")
    waste_contamination = fields.Many2one('waste.contamination.type', "Kontaminationsgruppe")
    product_qty = fields.Float(string="Quantity", default=1.0, required=True)
    contains_pop = fields.Boolean(string="POP", default=False)

    begleitschein_id = fields.Many2one(
        'waste.begleitschein', 'Begleitschein', index=True, ondelete='set null')

    vebsv_id = fields.Char(
        string="VEBSV ID", store=True, readonly=False, required=False)

    request_identifiers = fields.One2many(
        comodel_name='waste.line.request.identifier',
        inverse_name='line_id',
        string="Line Request Identifiers",
        copy=False, auto_join=False)

    def write_vebsv_id(self, vebsv_id: str):
        self.vebsv_id = vebsv_id

    def get_request_identifier(self, transfer_request_type: TransferRequestType):
        return self.request_identifiers.filtered(lambda r: r.name == transfer_request_type.name).uuid

    def add_request_identifier(self, transfer_request_type: TransferRequestType, uuid: str):
        name = transfer_request_type.name
        existing = self.request_identifiers.filtered(lambda r: r.name == name)
        if existing:
            existing.write({'uuid': uuid})
        else:
            self.write({'request_identifiers': [(0, 0, {'name': name, 'uuid': uuid})]})

    def get_shipment_item(self, line_item_number=0):
        return ShipmentItem(
            uuid.uuid4(),
            line_item_number,
            self.abfallart.gtin,
            self.waste_contamination.gtin,
            self.abfallart.note,
            self.vebsv_id,
            self.contains_pop,
            NetProperty("9008390104439", self.product_qty, "9008390100028")
        )

    def requires_reporting(self):
        return self.abfallart.dangerous or self.contains_pop


class BegleitscheinRequestIdentifier(models.Model):
    _name = 'waste.begleitschein.request.identifier'
    _description = 'Request Identifier'

    begleitschein_id = fields.Many2one(
        comodel_name='waste.begleitschein',
        string='Begleitschein',
        index=True,
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        string='Request Name',
        required=True,
        help="The name of request"
    )

    uuid = fields.Char(
        string='Request UUID',
        required=True,
        help="The uuid to identify the request"
    )


class LineRequestIdentifier(models.Model):
    _name = 'waste.line.request.identifier'
    _description = 'Request Identifier'

    line_id = fields.Many2one(
        comodel_name='waste.begleitschein.line',
        string='Begleitschein Line',
        index=True,
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        string='Request Name',
        required=True,
        help="The name of request"
    )

    uuid = fields.Char(
        string='Request UUID',
        required=True,
        help="The uuid to identify the request"
    )
