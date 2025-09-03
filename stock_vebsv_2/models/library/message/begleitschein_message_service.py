import logging

from zeep.exceptions import XMLParseError

from .begleitschein_ws_message import *

_logger = logging.getLogger(__name__)


class BegleitscheinMessageService():
    auth: Auth

    def __init__(self, auth):
        self.auth = auth

    def create_begleitschein(self, organisations: List[Organisation], shipment: Shipment, belgeitschein, partner_gln,
                             company_gln):
        message_envelope = create_ug_un_message(organisations, shipment)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,
                       MessageType.UEBERGABE_UEBERNAHME_MESSAGE)

    def start_transport(self, transport_mean, belgeitschein, partner_gln, company_gln, organisations:List[Organisation],
                        local_units: List[LocalUnit], shipment: Shipment, planned_waypoints: List[PlannedWaypoint], message_name):

        transport_mean = TransportMean("Strasse", "9008390100059")

        message_envelope = create_tr_message(organisations, local_units, shipment, belgeitschein.transport_uuid,
                                             message_name + "transport",
                                             planned_waypoints, transport_mean)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.transport_uuid,
                       belgeitschein.business_case_uuid, partner_gln,
                       company_gln, MessageType.TRANSPORT_MESSAGE)

        message_envelope = create_tr_st_message(belgeitschein.transport_uuid, transport_mean, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.transport_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln, MessageType.TRANSPORTSTART_MESSAGE)

    def end_transport(self, transport_mean, belgeitschein, partner_gln, company_gln, organisations: List[Organisation],
                      shipment: Shipment):
        message_envelope = create_tr_end_message(belgeitschein.transport_uuid, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.transport_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,
                       MessageType.TRANSPORTABSCHLUSS_MESSAGE)

        message_envelope = create_tr_end_message(belgeitschein.transport_uuid, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.transport_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,
                       MessageType.EMPFANGSBESTAETIGUNGS_MESSAGE)

        message_envelope = create_ug_best_message(shipment)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln,
                       MessageType.UEBERNAHMEBESTAETIGUNGS_MESSAGE)

    def cancel_begleitschein(self):
        # TODO: implement cancellation
        return

    def pull_news(self, own_gln, last_transaction_uuid):
        try:
            result = query_update(self.auth, last_transaction_uuid)
        except Exception as e:
            _logger.info("Refresh binding needs to be called")
            refresh_binding(self.auth)
            result = query_update(self.auth, last_transaction_uuid)

        changes = []
        for update in result["Update"]:
            if update["ForwardSharingEvent"]:
                last_transaction_uuid = update["ForwardSharingEvent"]['TransactionUUID']
                if any(party["RecipientID"] == own_gln for party in update["ForwardSharingEvent"]["SharedToParty"]):
                    document = retrieve_document(self.auth, last_transaction_uuid)
                    documentType = document["AuthenticatedDocument"]["DocumentUQ"]["DocumentHeader"]["DocumentTypeID"][
                        "_value_1"]
                    business_case_id = \
                        document["AuthenticatedDocument"]["DocumentUQ"]["DocumentHeader"]["ContextUUIDReference"][
                            "ContextUUID"]
                    _logger.info(
                        f"Message {documentType} found for business case {business_case_id}, with document id {business_case_id}")
                    if documentType == MessageType.UEBERGABE_UEBERNAHME_MESSAGE.value:
                        begleitschein = self.process_uebernahme_response(document)
                        if begleitschein:
                            changes.append({
                                'state': 'NEW',
                                'begleitschein': begleitschein,
                                'message': "Recived Übergabe Übernahme Message"
                            })
                    elif documentType == MessageType.TRANSPORT_MESSAGE.value:
                        changes.append({
                            'state': 'INFO',
                            'begleitschein': {
                                'business_case_uuid': business_case_id,
                            },
                            'message': "Recived transport message"
                        })
                    elif documentType == MessageType.TRANSPORTSTART_MESSAGE.value:
                        changes.append({
                            'state': 'INFO',
                            'begleitschein': {
                                'business_case_uuid': business_case_id,
                            },
                            'message': "Recived transport start message"
                        })
                    elif documentType == MessageType.TRANSPORTABSCHLUSS_MESSAGE.value:
                        changes.append({
                            'state': 'INFO',
                            'begleitschein': {
                                'business_case_uuid': business_case_id,
                            },
                            'message': "Recived transport abschluss message"
                        })
                    elif documentType == MessageType.UEBERNAHMEBESTAETIGUNGS_MESSAGE.value:
                        changes.append({
                            'state': 'INFO',
                            'begleitschein': {
                                'business_case_uuid': business_case_id,
                            },
                            'message': "Übernahme bestätigungs message"
                        })
            elif update["PostProcessingEvent"]:
                last_transaction_uuid = update["PostProcessingEvent"]['TransactionUUID']
                document = retrieve_document_validation_result(self.auth, last_transaction_uuid)
                _logger.warning(document)
            elif update["ProcessingEvent"]:
                last_transaction_uuid = update["ProcessingEvent"]['TransactionUUID']
                try:
                    document = retrieve_document_validation_result(self.auth, last_transaction_uuid)
                    _logger.warning(document)
                except Exception as e:
                    _logger.warning(e)
            else:
                _logger.info(f"recived unknown update{update}")

        return {
            'last_transaction_uuid': last_transaction_uuid,
            'changes': changes
        }

    def process_uebernahme_response(self, document):
        try:
            document_content = document["AuthenticatedDocument"]["DocumentUQ"]["DocumentContent"]
            xsd = load_message_xsd("/open_MessageFormatC.xsd")
            data = xsd.deserialize(document_content._value_1[0])
        except XMLParseError as e:
            _logger.error(
                f"Error while parsing XML response for document {document['AuthenticatedDocument']['DocumentUQ']['DocumentHeader']['DocumentUUID']}: {e.message}")
            return

        if not data['ListedData']:
            _logger.error(
                f"Error while parsing XML response for document {document['AuthenticatedDocument']['DocumentUQ']['DocumentHeader']['DocumentUUID']}: ListedData is empty")
            return
        org_data = {
            org['DocumentScopeAssignmentID']: org['ID'][0]['_value_1']
            for org in data['ListedData']['Organization']
            if org['DocumentScopeAssignmentID'] in ['handover', 'takeover'] and org['ID']
        }
        shipment = data['MessageData']['Shipment']
        begleitschein_lines = [
            {'abfallart': item['WasteTypeID']['_value_1'],
             'pop': item['ContainsPersistentOrganicPollutant'],
             'quantity': item['NetPropertyStatement']['ValueAssignmentStatement']['NumericValue']['_value_1']
             }
            for item in shipment['ShipmentItem']
        ]

        return {
            'handover_gln': org_data['handover'],
            'takeover_gln': org_data['takeover'],
            'business_case_uuid':
                document["AuthenticatedDocument"]["DocumentUQ"]["DocumentHeader"]["ContextUUIDReference"][
                    "ContextUUID"],
            'shipment_uuid': shipment['UUID'],
            'name': shipment['PredeterminedScopeAssignmentID']['_value_1'],
            'begleitschein_lines': begleitschein_lines
        }


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
