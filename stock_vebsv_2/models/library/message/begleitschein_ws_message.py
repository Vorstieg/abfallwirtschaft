import os
from enum import Enum

import requests
import zeep.xsd
from zeep import Client, Settings, xsd
from zeep.loader import load_external
from zeep.transports import Transport

from ..auth import Auth
from ..mappings import *

INTERFACE_VERSION = '1.09'
CONNECTOR_VERSION = '1.00'

WSDL_URL = "https://edmdemo.umweltbundesamt.at/messaging-ws/MessagingService?wsdl"
base_path = os.path.dirname(os.path.abspath(__file__))

session = requests.Session()
settings = Settings(strict=False)
transport = Transport(session=session)

client = Client(wsdl=WSDL_URL, settings=settings, transport=transport)

class MessageType(Enum):
    BESTELL_MESSAGE = '9008390117699'
    AVISO_MESSAGE = '9008390117705'
    BESTELLANTWORT_MESSAGE = '9008390117729'
    UEBERGABE_UEBERNAHME_MESSAGE = '9008390117712'
    TRANSPORT_MESSAGE = '9008390117439'
    TRANSPORTSTART_MESSAGE = '9008390117422'
    TRANSPORTABSCHLUSS_MESSAGE = '9008390117446'
    EMPFANGSBESTAETIGUNGS_MESSAGE = '9008390117453'
    UEBERNAHMEBESTAETIGUNGS_MESSAGE = '9008390117460'
    TRANSPORTABBRUCHS_MESSAGE = '9008390127445'
    ABLEHNUNGS_MESSAGE = '9008390127452'

def load_message_envelope(xsd_file):
    schema = load_message_xsd(xsd_file)
    return schema.get_element('ns0:MessageEnvelope')

def load_message_xsd(xsd_file):
    with open(base_path + "/api_definition" + xsd_file, 'rb') as f:
        xmlschema_doc = load_external(f, transport, base_path)
    return xsd.Schema(xmlschema_doc, transport=transport)


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


# Transport Message
def tr_message(organisations: List[Organisation], local_unit: List[LocalUnit], shipment: Shipment, transport_uuid,
               internal_id, planned_waypoint: List[PlannedWaypoint]):
    transport_mean = TransportMean("[transport label]", "[mode gtin]")

    MessageEnvelope = load_message_envelope("/open_MessageFormatD.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'ListedData': {
            'Organization': list(map(lambda x: x.parse(), organisations)),
            'LocalUnit': list(map(lambda x: x.parse(), local_unit)),
            'Shipment': shipment.parse_message_transport()
        },
        'MessageData': {
            'TransportMovement': {
                'UUID': transport_uuid,
                'PredeterminedScopeAssignmentID': internal_id,
                'TransportMeans': transport_mean.parse(),
                'PlannedWaypointEvent': list(map(lambda x: x.parse(), planned_waypoint)),
                'TransportItem': [
                    list(map(lambda x: x.parse_message_transport_item(), shipment.shipment_items))
                ]
            }
        }
    }))

# Transport start message
def tr_st_message(transport_uuid, transport_mean: TransportMean, actual_time: datetime):
    MessageEnvelope = load_message_envelope("/open_MessageFormatE.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'MessageData': {
            'TransportMovement': {
                'UUID': transport_uuid,
                'TransportMeans': transport_mean.parse(),
                'ActualWaypointEvent': {
                    'DateTime': actual_time.isoformat(),
                }
            }
        }
    }))


# Transport end message
# also transport empfangsbestätigung
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

def share_document(auth: Auth, transaction_uuid, message_envelope, object_uuid, context_uuid, recipient_gln,
                   sender_gln, documentTypeId: MessageType):
    """

    :param auth:
    :param transaction_uuid:
    :param message_envelope:
    :param object_uuid: for ug_un and ug_best_message ShipmentUUID, for transport related message, TransportMovementUUID
    :param context_uuid:
    :param recipient_gln:
    :param sender_gln:
    :param documentTypeId:
    :return:
    """
    CONTEXT_TYPE_ID = '9008390117408'  # Abholauftrag, Transportauftrag, Entsorgungsauftrag

    DOCUMENT_UUID = uuid.uuid4()  # Unique uuid for each document; when updating document, a new uuid is needed
    VERSION_BRAKCET_UUID = uuid.uuid4()  # Unique uuid for each document, needed for updating documents

    session.headers.update({
        'Authorization': auth.message_auth_header(f"{transaction_uuid}\n{DOCUMENT_UUID}",
                                                  f"{transaction_uuid}\n{DOCUMENT_UUID}\nShareDocument"),
    })

    request_data = {
        'ConnectorVersionID': CONNECTOR_VERSION,
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
                        '_value_1': documentTypeId.value
                    },
                    'DocumentUUID': DOCUMENT_UUID,
                    'VersionBracketUUID': VERSION_BRAKCET_UUID,
                    'VersionSequenceNumber': "0",
                    'DocumentOriginPartyID': sender_gln,
                    'ObjectUUID': object_uuid,
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
        'InterfaceVersionID': INTERFACE_VERSION,
        'ConnectorVersionID': CONNECTOR_VERSION,
        'UpdateRangeStartUUID': last_message_uuid
    }
    return client.service.QueryUpdate(**request_data)


def refresh_binding(auth):
    transaction_uuid = uuid.uuid4()
    session.headers.update({
        'Authorization': auth.message_auth_header(f"{transaction_uuid}\n", f"{transaction_uuid}\n\nRefreshBinding"),
    })

    request_data = {
        'InterfaceVersionID': INTERFACE_VERSION,
        'ConnectorVersionID': CONNECTOR_VERSION,
        'TransactionUUID': transaction_uuid
    }
    return client.service.RefreshBinding(**request_data)


def retrieve_document(auth, referred_transaction_uuid):
    session.headers.update({
        'Authorization': auth.message_auth_header(f"{referred_transaction_uuid}\n",
                                                  f"{referred_transaction_uuid}\n\nRetrieveDocument"),
    })

    request_data = {
        'InterfaceVersionID': INTERFACE_VERSION,
        'ConnectorVersionID': CONNECTOR_VERSION,
        'ReferredTransactionUUID': referred_transaction_uuid
    }
    return client.service.RetrieveDocument(**request_data)
