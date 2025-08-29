import logging

from zeep.exceptions import XMLParseError

from .begleitschein_ws_message import *

_logger = logging.getLogger(__name__)

class BegleitscheinMessageService():
    auth: Auth

    def __init__(self, auth):
        self.auth = auth

    def create_begleitschein(self, organisations: List[Organisation], shipment: Shipment, belgeitschein, partner_gln,
                             company_gln, planned_waypoints, message_name):
        message_envelope = ug_un_message(organisations, shipment)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,
                       MessageType.UEBERGABE_UEBERNAHME_MESSAGE)

        local_units = [LocalUnit("pickup_site", "9008390004500", "9008390109199"),
                       LocalUnit("dropoff_site", "9008390004494", "9008390109199")]
        message_envelope = tr_message(organisations, local_units, shipment, belgeitschein.transport_uuid,
                                      message_name + "transport",
                                      planned_waypoints)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.transport_uuid,
                       belgeitschein.business_case_uuid, partner_gln,
                       company_gln, MessageType.TRANSPORT_MESSAGE)

    def start_transport(self, transport_mean, belgeitschein, partner_gln, company_gln):
        message_envelope = tr_st_message(belgeitschein.transport_uuid, transport_mean, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.transport_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln, MessageType.TRANSPORTSTART_MESSAGE)

    def end_transport(self, transport_mean, belgeitschein, partner_gln, company_gln, organisations: List[Organisation],
                      shipment: Shipment):
        message_envelope = tr_end_message(belgeitschein.transport_uuid, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.transport_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,
                       MessageType.TRANSPORTABSCHLUSS_MESSAGE)

        message_envelope = tr_end_message(belgeitschein.transport_uuid, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.transport_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,
                       MessageType.EMPFANGSBESTAETIGUNGS_MESSAGE)

        message_envelope = ug_best_message(organisations, shipment)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,
                       MessageType.UEBERNAHMEBESTAETIGUNGS_MESSAGE)

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
                    document = retrieve_document(self.auth, referenced_transaction_uuid)
                    documentType = document["AuthenticatedDocument"]["DocumentUQ"]["DocumentHeader"]["DocumentTypeID"][
                        "_value_1"]
                    if documentType == MessageType.UEBERGABE_UEBERNAHME_MESSAGE.value:
                        self.process_uebernahme_response(document)

    def process_uebernahme_response(self, document):
        try:
            document_content = document["AuthenticatedDocument"]["DocumentUQ"]["DocumentContent"]
            xsd = load_message_xsd("/open_MessageFormatC.xsd")
            xmlschema_doc = xsd.deserialize(document_content._value_1[0])
        except XMLParseError as e:
            _logger.error(
                f"Error while parsing XML response for document {document['AuthenticatedDocument']['DocumentUQ']['DocumentHeader']['DocumentUUID']}: {e.message}")
            return
        print(xmlschema_doc)
        # todo: process Übernahme Message

class BegleitscheinMessageServiceMock(BegleitscheinMessageService):

    def create_begleitschein(self, organisations: List[Organisation], shipment: Shipment, belgeitschein, partner_gln,
                             company_gln, planned_waypoints, message_name):
        return

    def start_transport(self, transport_mean, belgeitschein, partner_gln, company_gln):
        return

    def end_transport(self, transport_mean, belgeitschein, partner_gln, company_gln, organisations: List[Organisation],
                      shipment: Shipment):
        return

    def cancel_begleitschein(self):
        return
