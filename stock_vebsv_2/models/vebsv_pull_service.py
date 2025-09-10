import logging
import os

from odoo import models, _, api
from odoo.exceptions import UserError

from .library.auth import Auth
from .library.message.begleitschein_message_service import BegleitscheinMessageService
from .library.mappings import *
from .library.transfer.begleitschein_ws_transfer import MessageType

_logger = logging.getLogger(__name__)


COMPANY_GLN_MISSING = "You need to have a GLN configured for your company"


class VebsvPullService(models.TransientModel):
    _name = "waste.vebsv.pull.service"
    _description = "VEBSV Pull Service"

    def pull_all_changes(self):
        companies = self.env['res.company'].search([])
        for company in companies:
            if company.partner_id.id_numbers:
                # This assumes that the first id_number is the GLN
                # TODO: A more robust implementation might require a specific type of id_number
                gln = company.partner_id.id_numbers[0].display_name
                self.pull_changes_for_company(gln)

    def pull_changes_for_company(self, company_gln):
        config_params = self.env['ir.config_parameter'].sudo()
        edm_last_transaction_uuid = config_params.get_param(
            'waste_management.edm_last_transaction_uuid') or "00000000-0000-0000-0000-000000000000"

        respone = self._get_begleitschein_message_service().pull_news(company_gln, edm_last_transaction_uuid)
        for line in respone["changes"]:
            if line["state"] == 'NEW':
                begleitschein = line["begleitschein"]
                handover_partner = self.env["res.partner.id_number"].search(
                    [("name", "=", begleitschein["handover_gln"])])
                takeover_partner = self.env["res.partner.id_number"].search(
                    [("name", "=", begleitschein["takeover_gln"])])
                new_begleitschein = self.env['waste.begleitschein'].create({
                    'name': f"{takeover_partner.partner_id.name.replace('\\', '').replace('/', '').replace(' ', '_')}_{begleitschein['name']}",
                    'source_partner_id': handover_partner.partner_id.id,
                    'target_partner_id': takeover_partner.partner_id.id,
                    'business_case_uuid': begleitschein["business_case_uuid"],
                    'self_is_main_organizer': False,
                    'begleitschein_lines': self._create_begleitschein_lines(begleitschein["begleitschein_lines"]),
                })
                new_begleitschein.message_post(
                    body=line["message"],
                    subtype_xmlid='mail.mt_note'
                )
            elif line["state"] == 'INFO':
                for begleitschein in (self.env['waste.begleitschein']
                        .search([("business_case_uuid", "=", line["begleitschein"]["business_case_uuid"])])):
                    begleitschein.message_post(body=line["message"], subtype_xmlid='mail.mt_note')
            elif line['state'] == 'UPDATE_SIGNAL':
                event_type = line['event_type']
                state_to_set = None
                # TODO This is mostly temporary, we still need to listen to BackwardSharingEvent for state changes
                # and decide when exactly which state will be active for whom
                if event_type == MessageType.HANDOVER_DECLARATION.value:
                    state_to_set = 'confirmed'
                elif event_type == MessageType.TRANSPORT_DECLARATION.value:
                    state_to_set = 'in_transport'
                elif event_type == MessageType.TAKEOVER_DECLARATION.value:
                    state_to_set = 'done'

                if state_to_set:
                    begleitschein_line = self.env["waste.begleitschein.line"].search([("vebsv_id", "=", line["vebsv_id"])], limit=1)
                    if begleitschein_line:
                        begleitschein_line.begleitschein_id.state = state_to_set

        config_params.set_param('waste_management.edm_last_transaction_uuid', respone["last_transaction_uuid"])

    def _create_begleitschein_lines(self, lines_data):
        lines = []
        for l in lines_data:
            waste_type = self.env['waste.type'].search([("gtin", "=", l["abfallart"])], limit=1)
            line_vals = {
                'product_qty': l["quantity"],
                'contains_pop': l["pop"],
                'vebsv_id': l["vebsv_id"],
                'abfallart': waste_type.id if waste_type else False,
            }
            lines.append((0, 0, line_vals))
        return lines

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
