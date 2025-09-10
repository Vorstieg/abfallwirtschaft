import logging
import os
from enum import Enum

import requests
import zeep.xsd
from zeep import Client, Settings, xsd
from zeep.loader import load_external
from zeep.transports import Transport

from ..auth import Auth
from ..mappings import *
from ..zeep_pluggins import ZeepLoggingPlugin

_logger = logging.getLogger(__name__)

INTERFACE_VERSION = '1.09'
CONNECTOR_VERSION = '1.00'

WSDL_URL = "https://edmdemo.umweltbundesamt.at/messaging-ws/MessagingService?wsdl"
base_path = os.path.dirname(os.path.abspath(__file__))

session = requests.Session()
settings = Settings(strict=False)
transport = Transport(session=session)

client = Client(wsdl=WSDL_URL, settings=settings, transport=transport, plugins=[ZeepLoggingPlugin()])


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
def create_ug_un_message(organisations: List[Organisation], local_unit: List[LocalUnit], shipment: Shipment,
                         sms_solution=False):
    MessageEnvelope = load_message_envelope("/open_MessageFormatC.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'ListedData': {
            'Organization': list(map(lambda x: x.parse(), organisations)),
            'LocalUnit': list(map(lambda x: x.parse(), local_unit))
        },
        'MessageData': {
            'Shipment': shipment.parse(sms_solution)
        }
    }))


def create_un_best_message(shipment: Shipment):
    MessageEnvelope = load_message_envelope("/open_MessageFormatC.xsd")
    return zeep.xsd.AnyObject(MessageEnvelope, MessageEnvelope(**{
        'MessageData': {
            'Shipment': shipment.parse_message_uebernahme()
        }
    }))


# Transport Message
def create_tr_message(organisations: List[Organisation], local_unit: List[LocalUnit], shipment: Shipment,
                      transport_uuid,
                      internal_id, planned_waypoint: List[PlannedWaypoint], transport_mean: TransportMean, carrier_reference:str):
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
                ],
                'CarrierPartyReferenceID': carrier_reference
            }
        }
    }))


# Transport start message
def create_tr_st_message(transport_uuid, transport_mean: TransportMean, actual_time: datetime):
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
def create_tr_end_message(transport_uuid, actual_time: datetime):
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


def share_document(auth: Auth, transaction_uuid, message_envelope, object_uuid, context_uuid, recipients: List[Recipient],
                   sender_gln: str, document_type_id: MessageType, begleitschein, message_suffix: str = ""):
    """
    :param auth:
    :param transaction_uuid:
    :param message_envelope:
    :param object_uuid: for ug_un and ug_best_message ShipmentUUID, for transport related message, TransportMovementUUID
    :param context_uuid:
    :param recipients: List of all recipients
    :param sender_gln:
    :param document_type_id:
    :param begleitschein:
    :param message_suffix:
    :return:
    """
    CONTEXT_TYPE_ID = '9008390117408'  # Abholauftrag, Transportauftrag, Entsorgungsauftrag

    DOCUMENT_UUID = uuid.uuid4()
    version_bracket_uuid = str(uuid.uuid4())
    version_sequence_number = 0

    begleitschein.add_request_identifier(document_type_id, message_suffix, version_bracket_uuid)

    session.headers.update({
        'Authorization': auth.message_auth_header(f"{transaction_uuid}\n{DOCUMENT_UUID}",
                                                  f"{transaction_uuid}\n{DOCUMENT_UUID}\nShareDocument"),
    })

    request_data = {
        'ConnectorVersionID': CONNECTOR_VERSION,
        'TransactionUUID': transaction_uuid,
        'InterfaceVersionID': "1.10",
        'Recipient': [recipient.parse() for recipient in recipients],
        'AuthenticatedDocument': {
            'DocumentUQ': {
                'DocumentHeader': {
                    'DocumentTypeID': {
                        'collectionID': '2551',
                        '_value_1': document_type_id.value
                    },
                    'DocumentUUID': DOCUMENT_UUID,
                    'VersionBracketUUID': version_bracket_uuid,
                    'VersionSequenceNumber': version_sequence_number,
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
    _logger.info(f"Share document request for type {document_type_id} for business case {context_uuid}")
    return client.service.ShareDocument(**request_data)


def share_document_cancellation(auth: Auth, transaction_uuid, version_bracket_uuid, recipients, sender_gln, reason):
    user_string = f"{transaction_uuid}\n{version_bracket_uuid}"
    connector_string = f"{transaction_uuid}\n{version_bracket_uuid}\nShareDocumentCancellation"

    session.headers.update({
        'Authorization': auth.message_auth_header(user_string, connector_string),
    })

    request_data = {
        'ConnectorVersionID': CONNECTOR_VERSION,
        'TransactionUUID': transaction_uuid,
        'InterfaceVersionID': "1.10",
        'Recipient': [recipient.parse() for recipient in recipients],
        'AuthenticatedCancellation': {
            'DocumentUQ': {
                'VersionBracketUUID': version_bracket_uuid,
                'ChangeReasonID': {
                    'collectionID': '7521',
                    '_value_1': reason.gtin
                },
                'DocumentOriginPartyID': sender_gln
            }
        }
    }

    _logger.info(f"Share document cancellation request for version bracket {version_bracket_uuid}")
    return client.service.ShareDocumentCancellation(**request_data)


def query_update(auth, last_message_uuid):
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


def retrieve_document_validation_result(auth, referred_transaction_uuid):
    session.headers.update({
        'Authorization': auth.message_auth_header(f"{referred_transaction_uuid}\n",
                                                  f"{referred_transaction_uuid}\n\nQueryDocumentValidationResult"),
    })

    request_data = {
        'InterfaceVersionID': INTERFACE_VERSION,
        'ConnectorVersionID': CONNECTOR_VERSION,
        'ReferredTransactionUUID': referred_transaction_uuid
    }
    return client.service.QueryDocumentValidationResult(**request_data)
