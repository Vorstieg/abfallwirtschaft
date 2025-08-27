import logging
import os

import requests
import zeep.xsd
from zeep import Client, Settings, xsd
from zeep.loader import load_external
from zeep.transports import Transport

from ..auth import Auth
from ..structure import *

_logger = logging.getLogger(__name__)

WSDL_URL = "https://edmdemo.umweltbundesamt.at/messaging-ws/MessagingService?wsdl"
base_path = os.path.dirname(os.path.abspath(__file__))

session = requests.Session()
settings = Settings(strict=False)
transport = Transport(session=session)

client = Client(wsdl=WSDL_URL, settings=settings, transport=transport)


def load_message_envelope(xsd_file):
    with open(base_path + xsd_file, 'rb') as f:
        xmlschema_doc = load_external(f, transport, base_path)
    schema = xsd.Schema(xmlschema_doc, transport=transport)
    MessageEnvelope = schema.get_element('ns0:MessageEnvelope')
    return MessageEnvelope


# Übergabe-/Übernahme-Message
def ug_un_message(organisations: List[Organisation], shipment: Shipment):
    MessageEnvelope = load_message_envelope("/open_MessageFormatC.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'ListedData': {
            'Organization': list(map(lambda x: x.parse(), organisations))
        },
        'MessageData': {
            'Shipment': shipment.parse()
        }
    }))


def ug_best_message(organisations: List[Organisation], shipment: Shipment):
    MessageEnvelope = load_message_envelope("/open_MessageFormatC.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'MessageData': {
            'Shipment': shipment.parse()
        }
    }))


# Übergabe bestätigungs meassage
def tr_message(organisations: List[Organisation], local_unit: List[LocalUnit], shipment: Shipment, transport_uuid,
               internal_id, planned_waypoint: List[PlannedWaypoint], transport_item: List[TransportItem]):
    transport_mean = TransportMean("[transport label]", "[mode gtin]")

    MessageEnvelope = load_message_envelope("/open_MessageFormatD.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'ListedData': [
            list(map(lambda x: x.parse(), organisations)) +
            list(map(lambda x: x.parse(), local_unit)) +
            [{'Shipment': shipment.parse()}]
        ],
        'MessageData': {
            'TransportMovement': {
                'UUID': transport_uuid,
                'PredeterminedScopeAssignmentID': internal_id,
                'TransportMeans': transport_mean,
                'PlannedWaypointEvent': [
                    list(map(lambda x: x.parse(), planned_waypoint))
                ],
                'TransportItem': [
                    list(map(lambda x: x.parse(), transport_item))
                ]
            }
        }
    }))


def tr_st_message(transport_uuid, transport_mean: TransportMean, actual_time: datetime):
    MessageEnvelope = load_message_envelope("/open_MessageFormatE.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'MessageData': {
            'TransportMovement': {
                'UUID': transport_uuid,
                'TransportMeans': transport_mean,
                'ActualWaypointEvent': {
                    'DateTime': actual_time.isoformat(),
                }
            }
        }
    }))


# Transport start message
def tr_end_message(transport_uuid, actual_time: datetime):
    MessageEnvelope = load_message_envelope("/open_MessageFormatF.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'MessageData': {
            'TransportMovement': {
                'UUID': transport_uuid,
                'ActualWaypointEvent': {
                    'DateTime': actual_time.isoformat(),
                }
            }
        }
    }))


# Transport end message
# also transport empfangsbestätigung
def share_document(auth: Auth, transaction_uuid, message_envelope, shipment_uuid, context_uuid, recipient_gln,
                   sender_gln):
    UG_UN_MESSAGE_ID = '9008390117712'
    CONTEXT_TYPE_ID = '9008390117408'  # Abholauftrag, Transportauftrag, Entsorgungsauftrag

    DOCUMENT_UUID = uuid.uuid4()  # Unique uuid for each document; when updating document, a new uuid is needed
    VERSION_BRAKCET_UUID = uuid.uuid4()  # Unique uuid for each document, needed for updating documents

    session.headers.update({
        'Authorization': auth.message_auth_header(f"{transaction_uuid}\n{DOCUMENT_UUID}",
                                                  f"{transaction_uuid}\n{DOCUMENT_UUID}\nShareDocument"),
    })

    request_data = {
        'ConnectorVersionID': "1.00",
        'TransactionUUID': transaction_uuid,
        'InterfaceVersionID': "1.10",
        'Recipient': {
            'RecipientID': recipient_gln,
            'TransactionPurposeCategoryID': {
                'collectionID': '2976',
                '_value_1': 'request'  # two possible values: request and inform
            }
        },
        'AuthenticatedDocument': {
            'DocumentUQ': {
                'DocumentHeader': {
                    'DocumentTypeID': {
                        'collectionID': '2551',
                        '_value_1': UG_UN_MESSAGE_ID  # changes, based on which message is sent
                    },
                    'DocumentUUID': DOCUMENT_UUID,
                    'VersionBracketUUID': VERSION_BRAKCET_UUID,
                    'VersionSequenceNumber': "0",
                    'DocumentOriginPartyID': sender_gln,
                    'ObjectUUID': shipment_uuid,
                    'ContextUUIDReference': {
                        'ContextUUID': context_uuid,
                        'ContextTypeID': {
                            'collectionID': '7263',
                            '_value_1': CONTEXT_TYPE_ID
                        }
                    }
                },
                'DocumentContent': {
                    '_value_1': message_envelope
                }
            }
        }

    }
    return client.service.ShareDocument(**request_data)


def query_update(auth, last_message_uuid="00000000-0000-0000-0000-000000000000"):
    session.headers.update({
        'Authorization': auth.message_query_update_special_case_auth_header(last_message_uuid),
    })

    request_data = {
        'InterfaceVersionID': '1.09',
        'ConnectorVersionID': '1.00',
        'UpdateRangeStartUUID': last_message_uuid
    }
    return client.service.QueryUpdate(**request_data)


def refresh_binding(auth):
    transaction_uuid = uuid.uuid4()
    session.headers.update({
        'Authorization': auth.message_auth_header(f"{transaction_uuid}\n", f"{transaction_uuid}\n\nRefreshBinding"),
    })

    request_data = {
        'InterfaceVersionID': '1.09',
        'ConnectorVersionID': '1.00',
        'TransactionUUID': transaction_uuid
    }
    return client.service.RefreshBinding(**request_data)


def retrieve_document(auth, referred_transaction_uuid):
    session.headers.update({
        'Authorization': auth.message_auth_header(f"{referred_transaction_uuid}\n",
                                                  f"{referred_transaction_uuid}\n\nRetrieveDocument"),
    })

    request_data = {
        'InterfaceVersionID': '1.09',
        'ConnectorVersionID': '1.00',
        'ReferredTransactionUUID': referred_transaction_uuid
    }
    return client.service.RetrieveDocument(**request_data)


class BegleitScheinMessageService():
    auth: Auth

    def __init__(self, auth):
        self.auth = auth

    def create_begleitschein(self, organisations: List[Organisation], shipment: Shipment, belgeitschein, partner_gln,
                             company_gln,
                             planned_waypoints, transport_items, message_name):
        message_envelope = ug_un_message(organisations, shipment)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln)

        local_units = [LocalUnit("pickup_site", "9008390004500", "9008390109199"),
                       LocalUnit("dropoff_site", "9008390004494", "9008390109199")]
        message_envelope = tr_message(organisations, local_units, shipment, belgeitschein.transport_uuid,
                                      message_name + "transport",
                                      planned_waypoints, transport_items)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln,
                       company_gln)

    def start_transport(self, transport_mean, belgeitschein, partner_gln, company_gln):
        message_envelope = tr_st_message(belgeitschein.transport_uuid, transport_mean, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln)

    def end_transport(self, transport_mean, belgeitschein, partner_gln, company_gln, organisations: List[Organisation],
                      shipment: Shipment):
        message_envelope = tr_end_message(belgeitschein.transport_uuid, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln)

        message_envelope = tr_end_message(belgeitschein.transport_uuid, datetime.now())

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln)

        message_envelope = ug_best_message(organisations, shipment)

        share_document(self.auth, uuid.uuid4(), message_envelope, belgeitschein.shipment_uuid,
                       belgeitschein.business_case_uuid, partner_gln, company_gln)

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
