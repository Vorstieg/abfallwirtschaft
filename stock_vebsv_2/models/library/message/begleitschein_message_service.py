import logging
import os

import requests
import zeep.xsd
from zeep import Client, Settings, xsd
from zeep.loader import load_external
from zeep.transports import Transport

from ..auth import Auth
from ..structure import *
from .begleitschein_ws_message import *

_logger = logging.getLogger(__name__)

class BegleitScheinMessageService():
    auth: Auth

    def __init__(self, auth):
        self.auth = auth

    def create_begleitschein(self, organisations: List[Organisation], shipment: Shipment, belgeitschein, partner_gln,
                             company_gln,
                             planned_waypoints, transport_items, message_name):
        message_envelope = ug_un_message(organisations, shipment)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln, "9008390117712")

        local_units = [LocalUnit("pickup_site", "9008390004500", "9008390109199"),
                       LocalUnit("dropoff_site", "9008390004494", "9008390109199")]
        message_envelope = tr_message(organisations, local_units, shipment, belgeitschein.transport_uuid,
                                      message_name + "transport",
                                      planned_waypoints, transport_items)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln,
                       company_gln, "9008390117439")

    def start_transport(self, transport_mean, belgeitschein, partner_gln, company_gln):
        message_envelope = tr_st_message(belgeitschein.transport_uuid, transport_mean, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln, "9008390117422")

    def end_transport(self, transport_mean, belgeitschein, partner_gln, company_gln, organisations: List[Organisation],
                      shipment: Shipment):
        message_envelope = tr_end_message(belgeitschein.transport_uuid, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln, "9008390117446")

        message_envelope = tr_end_message(belgeitschein.transport_uuid, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,"9008390117453")

        message_envelope = ug_best_message(organisations, shipment)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,"9008390117460")

    def cancel_begleitschein(self):
        # TODO: implement cancellation
        return

    def pull_news(self, own_gln):
        try:
            result = query_update(self.auth)
        except Exception as e:
            _logger.info("Refresh binding needs to be called")
            refresh_binding(self.auth)
            result = query_update(self.auth)

        for update in result["Update"]:
            if update["ForwardSharingEvent"]:
                if any(party["RecipientID"] == own_gln for party in update["ForwardSharingEvent"]["SharedToParty"]):
                    referenced_transaction_uuid = update["ForwardSharingEvent"]['TransactionUUID']
                    print(retrieve_document(self.auth, referenced_transaction_uuid))

        return result


class BegleitScheinMockMessageService(BegleitScheinMessageService):

    def create_begleitschein(self, organisations: List[Organisation], shipment: Shipment, belgeitschein, partner_gln,
                             company_gln, planned_waypoints, transport_items, message_name):
        return

    def start_transport(self, transport_mean, belgeitschein, partner_gln, company_gln):
        return

    def end_transport(self, transport_mean, belgeitschein, partner_gln, company_gln, organisations: List[Organisation],
                      shipment: Shipment):
        return

    def cancel_begleitschein(self):
        return
