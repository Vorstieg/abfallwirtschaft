from zeep.exceptions import XMLParseError, Fault

from odoo.addons.product_waste_registry.models.core_data.waste_revocation_reason import WasteRevocationReason
from .begleitschein_ws_message import *
from ..vebsv_begleitschein import VebsvBegleitschein, MessageRequestType, VebsvPartner

_logger = logging.getLogger(__name__)


class BegleitscheinMessageService:
    auth: Auth

    def __init__(self, auth):
        self.auth = auth

    def create_begleitschein(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, sms_telephone_number):
        if begleitschein.is_dropshipping_with_two_legs():
            self._ug_un_message(begleitschein, sms_telephone_number, sender, True, "_source_leg")
            self._ug_un_message(begleitschein, False, sender, False, "_target_leg")
        else:
            self._ug_un_message(begleitschein, sms_telephone_number, sender)

    def cancel_create_begleitschein(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner,
                                    reason: WasteRevocationReason):
        if begleitschein.is_dropshipping_with_two_legs():
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(
                                            MessageRequestType.UEBERGABE_UEBERNAHME_MESSAGE,
                                            "_source_leg"),
                                        begleitschein.restricted_recipient_glns(sender, source_leg=True),
                                        sender.get_person_gln(), reason)
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(
                                            MessageRequestType.UEBERGABE_UEBERNAHME_MESSAGE,
                                            "_target_leg"),
                                        begleitschein.restricted_recipient_glns(sender, source_leg=False),
                                        sender.get_person_gln(), reason)
        else:
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(
                                            MessageRequestType.UEBERGABE_UEBERNAHME_MESSAGE),
                                        begleitschein.restricted_recipient_glns(sender, source_leg=True),
                                        sender.get_person_gln(), reason)

    def start_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner):
        message_envelope = create_tr_st_message(begleitschein.transport_uuid, begleitschein.transport_mean(),
                                                datetime.now())
        share_document(self.auth, uuid.uuid4(), message_envelope, begleitschein.transport_uuid,
                       begleitschein.business_case_uuid, begleitschein.all_recipient_glns(sender),
                       sender.get_person_gln(),
                       MessageType.TRANSPORTSTART_MESSAGE, begleitschein)

    def declare_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, message_name):
        if begleitschein.is_dropshipping_with_two_legs():
            self._declare_transport(begleitschein, sender, message_name, True, "_source_leg")
            self._declare_transport(begleitschein, sender, message_name, False, "_target_leg")
        else:
            self._declare_transport(begleitschein, sender, message_name)

    def cancel_start_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner,
                               reason: WasteRevocationReason):
        share_document_cancellation(self.auth, uuid.uuid4(),
                                    begleitschein.get_request_identifier(MessageRequestType.TRANSPORTSTART_MESSAGE),
                                    begleitschein.all_recipient_glns(sender),
                                    sender.get_person_gln(), reason)

    def cancel_declare_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner,
                                 reason: WasteRevocationReason):
        if begleitschein.is_dropshipping_with_two_legs():
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(MessageRequestType.TRANSPORT_MESSAGE,
                                                                             "_source_leg"),
                                        begleitschein.restricted_recipient_glns(sender, source_leg=True),
                                        sender.get_person_gln(), reason)
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(MessageRequestType.TRANSPORT_MESSAGE,
                                                                             "_target_leg"),
                                        begleitschein.restricted_recipient_glns(sender, source_leg=False),
                                        sender.get_person_gln(), reason)
        else:
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(MessageRequestType.TRANSPORT_MESSAGE),
                                        begleitschein.restricted_recipient_glns(sender, source_leg=True),
                                        sender.get_person_gln(), reason)

    def end_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner):
        if sender.is_carrier(begleitschein):
            message_envelope = create_tr_end_message(begleitschein.transport_uuid, datetime.now())
            share_document(self.auth, uuid.uuid4(), message_envelope, begleitschein.transport_uuid,
                           begleitschein.business_case_uuid, begleitschein.all_recipient_glns(sender),
                           sender.get_person_gln(),
                           MessageType.TRANSPORTABSCHLUSS_MESSAGE, begleitschein)
        if sender.is_target(begleitschein):
            message_envelope = create_tr_end_message(begleitschein.transport_uuid, datetime.now())
            share_document(self.auth, uuid.uuid4(), message_envelope, begleitschein.transport_uuid,
                           begleitschein.business_case_uuid, begleitschein.restricted_recipient_glns(sender),
                           sender.get_person_gln(),
                           MessageType.EMPFANGSBESTAETIGUNGS_MESSAGE, begleitschein)
            message_envelope = create_un_best_message(begleitschein.get_shipment())
            share_document(self.auth, uuid.uuid4(), message_envelope, begleitschein.shipment_uuid,
                           begleitschein.business_case_uuid, begleitschein.restricted_recipient_glns(sender),
                           sender.get_person_gln(),
                           MessageType.UEBERNAHMEBESTAETIGUNGS_MESSAGE, begleitschein)

    def cancel_end_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner,
                             reason: WasteRevocationReason):
        if sender.is_target(begleitschein):
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(
                                            MessageRequestType.UEBERNAHMEBESTAETIGUNGS_MESSAGE),
                                        begleitschein.restricted_recipient_glns(sender),
                                        sender.get_person_gln(), reason)
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(
                                            MessageRequestType.EMPFANGSBESTAETIGUNGS_MESSAGE),
                                        begleitschein.restricted_recipient_glns(sender),
                                        sender.get_person_gln(), reason)
        if sender.is_carrier(begleitschein):
            share_document_cancellation(self.auth, uuid.uuid4(),
                                        begleitschein.get_request_identifier(
                                            MessageRequestType.TRANSPORTABSCHLUSS_MESSAGE),
                                        begleitschein.all_recipient_glns(sender),
                                        sender.get_person_gln(), reason)

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
                    try:
                        document = retrieve_document(self.auth, last_transaction_uuid)
                    except Fault as fault:
                        _logger.error(f"Error while fetching document{last_transaction_uuid}: {fault.message}")
                        continue

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
                            'state': 'UPDATE',
                            'begleitschein': {
                                'business_case_uuid': business_case_id,
                                'state': 'in_transport'
                            },
                            'message': "Recived transport start message"
                        })
                    elif documentType == MessageType.TRANSPORTABSCHLUSS_MESSAGE.value:
                        changes.append({
                            'state': 'UPDATE',
                            'begleitschein': {
                                'business_case_uuid': business_case_id,
                                'state': 'transport_complete'
                            },
                            'message': "Recived transport abschluss message"
                        })
                    elif documentType == MessageType.UEBERNAHMEBESTAETIGUNGS_MESSAGE.value:
                        changes.append({
                            'state': 'UPDATE',
                            'begleitschein': {
                                'business_case_uuid': business_case_id,
                                'state': 'done'
                            },
                            'message': "Übernahme bestätigungs message"
                        })
            elif update["PostProcessingEvent"]:
                last_transaction_uuid = update["PostProcessingEvent"]['TransactionUUID']
                document = retrieve_document_validation_result(self.auth, last_transaction_uuid)
                _logger.warning(document)
            elif update["ProcessingEvent"]:
                last_transaction_uuid = update["ProcessingEvent"]['TransactionUUID']
                _logger.warning(update["ProcessingEvent"]["StatusDescription"]["_value_1"])
            elif update["BackwardSharingEvent"]:
                last_transaction_uuid = update["BackwardSharingEvent"]['TransactionUUID']
                _logger.info(f"recived backward sharing event for {last_transaction_uuid}")
            elif update["UpdateSignalEvent"]:
                last_transaction_uuid = update["UpdateSignalEvent"]['TransactionUUID']
                changes.append({
                    'state': 'UPDATE_SIGNAL',
                    'event_type': update["UpdateSignalEvent"]['TriggerEventTypeID']['_value_1'],
                    'vebsv_id': update["UpdateSignalEvent"]['AffectedObjectID'],
                    'message': "Received UpdateSignalEvent"
                })
            else:
                _logger.info(f"received unknown update{update}")

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
        }
        shipment = data['MessageData']['Shipment']
        begleitschein_lines = [
            {'abfallart': item['WasteTypeID']['_value_1'],
             'vebsv_id': item['ConsignmentNoteReferenceID']['_value_1'] if item['ConsignmentNoteReferenceID'] else None,
             'pop': item['ContainsPersistentOrganicPollutant'],
             'quantity': item['NetPropertyStatement']['ValueAssignmentStatement']['NumericValue']['_value_1']
             }
            for item in shipment['ShipmentItem']
        ]
        take_over_reference = shipment['TakeOverPartyReferenceID']['_value_1']
        hand_over_reference = shipment['HandOverPartyReferenceID']['_value_1']

        return {
            'handover_gln': org_data[hand_over_reference],
            'takeover_gln': org_data[take_over_reference],
            'business_case_uuid':
                document["AuthenticatedDocument"]["DocumentUQ"]["DocumentHeader"]["ContextUUIDReference"][
                    "ContextUUID"],
            'shipment_uuid': shipment['UUID'],
            'organizing_partner_gln': document["AuthenticatedDocument"]["DocumentUQ"]["DocumentHeader"][
                "DocumentOriginPartyID"],
            'name': shipment['PredeterminedScopeAssignmentID']['_value_1'],
            'begleitschein_lines': begleitschein_lines
        }

    def _ug_un_message(self, begleitschein, sms_telephone_number, sender: VebsvPartner, first_leg=True,
                       suffix: str = ""):
        message_envelope = create_ug_un_message(begleitschein.selected_organisations(first_leg),
                                                begleitschein.selected_local_units(dropoff=not first_leg),
                                                begleitschein.get_shipment(),
                                                sms_telephone_number)
        share_document(self.auth, uuid.uuid4(), message_envelope, begleitschein.shipment_uuid,
                       begleitschein.business_case_uuid,
                       begleitschein.restricted_recipient_glns(sender, sms_telephone_number, first_leg),
                       sender.get_person_gln(),
                       MessageType.UEBERGABE_UEBERNAHME_MESSAGE, begleitschein, suffix)

    def _declare_transport(self, begleitschein, sender: VebsvPartner, message_name, first_leg=False, suffix: str = ""):
        message_envelope = create_tr_message(begleitschein.selected_organisations(first_leg),
                                             begleitschein.selected_local_units(dropoff=not first_leg),
                                             begleitschein.get_shipment(),
                                             begleitschein.transport_uuid,
                                             message_name + "transport",
                                             begleitschein.selected_waypoints(dropoff=not first_leg),
                                             begleitschein.transport_mean(),
                                             begleitschein.carrier_reference())
        share_document(self.auth, uuid.uuid4(), message_envelope, begleitschein.transport_uuid,
                       begleitschein.business_case_uuid,
                       begleitschein.restricted_recipient_glns(sender, source_leg=first_leg),
                       sender.get_person_gln(),
                       MessageType.TRANSPORT_MESSAGE, begleitschein, suffix)
