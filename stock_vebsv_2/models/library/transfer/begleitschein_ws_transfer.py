from datetime import datetime
from enum import Enum
from typing import List, Union

import requests
from zeep import Client, Settings
from zeep.transports import Transport

from odoo.addons.product_waste_registry.models.core_data.waste_revocation_reason import WasteRevocationReason
from ..auth import Auth
from ..mappings import Organisation, LocalUnit, ShipmentItem, TransportMean, PlannedWaypoint
from ..zeep_pluggins import ZeepLoggingPlugin


class TransferMessageType(Enum):
    HANDOVER_DECLARATION = '9008390116289'
    TRANSPORT_DECLARATION = '9008390116272'
    TRANSPORT_START_DECLARATION = '9008390116326'
    TAKEOVER_DECLARATION = '9008390116319'
    DROPSHIPPING_DECLARATION = '9008390132197'


WSDL_URL = "https://edmdemo.umweltbundesamt.at/vebsv-ws/TransferOfWasteService?wsdl"

INTERFACE_VERSION = '1.09'
CONNECTOR_VERSION = '1.00'

settings = Settings(strict=False)
session = requests.Session()
transport = Transport(session=session)

client = Client(wsdl=WSDL_URL, settings=settings, transport=transport, plugins=[ZeepLoggingPlugin()])

# Collection IDs
COLLECTION_ID_EVENT_TYPE_PHYSICAL = '8926'
COLLECTION_ID_TRANSPORT_MEAN_TYPE = '2939'
COLLECTION_ID_WAYPOINT_TYPE = '8501'
COLLECTION_ID_DOCUMENT_CREATION = '1239'
COLLECTION_ID_DOCUMENT_TYPE = '5064'
COLLECTION_ID_VEBSV_ID = '9008390104026'

# Role IDs
ROLE_ID_VEBSV_ID = '9008390104576'
ROLE_ID_HANDOVER_PARTY = '9008390104705'
ROLE_ID_TAKEOVER_PARTY = '9008390104712'
ROLE_ID_PICKUP_SITE = '9008390108338'
ROLE_ID_DROPOFF_SITE = '9008390108345'
ROLE_ID_TRANSPORTEUR = '9008390116906'
ROLE_ID_DROPSHIP = '9008390117231'
ROLE_ID_VERANLASSER = '9008390116913'
ROLE_ID_TRANSPORT_EVENT = '9008390104576'
ROLE_ID_PARTY_IN_TRANSPORT = '9008390104583'
ROLE_ID_LOCATION_IN_TRANSPORT = '9008390108321'
ROLE_ID_DOCUMENT_CREATOR = '9008390104583'

# Type IDs
TYPE_ID_PHYSICAL_EVENT = '9008390116371'
TYPE_ID_LOADING_WAYPOINT = '9008390116395'
TYPE_ID_UNLOADING_WAYPOINT = '9008390116401'
TYPE_ID_DOCUMENT_CREATION = '9008390106594'
TYPE_ID_STRECKENGESCHAEFTS_MELDUNG = '9008390132197'

# Object Designations & Type Names
OBJECT_DESIGNATION_PHYSICAL = 'Physisch'
OBJECT_DESIGNATION_VEBSV_ID = 'VEBSV-ID'
OBJECT_DESIGNATION_DOCUMENT_CREATION = 'Dokumenterstellung'
OBJECT_TYPE_NAME_UNTERNEHMEN = 'Unternehmen'
OBJECT_TYPE_NAME_STANDORT = 'Standort'
OBJECT_TYPE_NAME_EINZELTRANSPORT = 'Einzeltransport'
OBJECT_TYPE_STRECKENGESCHAEFTS_MELDUNG = 'Streckengeschäftsmeldung'


def request_waste_transfer_id(auth: Auth, transaction_uuid: str):
    session.headers.update({
        'Authorization': auth.transfer_auth_header(transaction_uuid, "RequestWasteTransferID"),
    })
    request_data = {
        'ConnectorVersionID': CONNECTOR_VERSION,
        'TransactionUUID': transaction_uuid
    }
    return client.service.RequestWasteTransferID(**request_data)


def create_handover_declaration_message(organisations: List[Organisation], local_units: List[LocalUnit],
                                        shipment_item: ShipmentItem, vebsv_id: str):
    listed_data = _create_listed_data(organisations, local_units)
    scope_refs = [
        _create_scope_reference(ROLE_ID_HANDOVER_PARTY, OBJECT_TYPE_NAME_UNTERNEHMEN, 'handover'),
        _create_scope_reference(ROLE_ID_TAKEOVER_PARTY, OBJECT_TYPE_NAME_UNTERNEHMEN, 'takeover'),
        _create_scope_reference(ROLE_ID_PICKUP_SITE, OBJECT_TYPE_NAME_STANDORT, 'pickup_site'),
    ]
    type_a_event = _create_type_a_event(shipment_item, vebsv_id, scope_refs)
    environmental_data = {'TypeAEvent': type_a_event}
    return _build_environmental_data_instance(TransferMessageType.HANDOVER_DECLARATION.value, listed_data, environmental_data,
                                              "handover")


def create_dropship_declaration_message(organisations: List[Organisation], vebsv_id: str):
    listed_data = _create_listed_data(organisations, [])
    scope_refs = [
        _create_scope_reference(ROLE_ID_HANDOVER_PARTY, OBJECT_TYPE_NAME_UNTERNEHMEN, 'handover'),
        _create_scope_reference(ROLE_ID_TAKEOVER_PARTY, OBJECT_TYPE_NAME_UNTERNEHMEN, 'takeover'),
        (_create_scope_reference(ROLE_ID_DROPSHIP, OBJECT_TYPE_NAME_UNTERNEHMEN, organisation.role)
         for organisation in organisations if "dropship" in organisation)
    ]
    type_a_event = {
        'TypeID': _create_type_id(COLLECTION_ID_DOCUMENT_TYPE, TYPE_ID_STRECKENGESCHAEFTS_MELDUNG,
                                  OBJECT_TYPE_STRECKENGESCHAEFTS_MELDUNG),
        'Date': datetime.now().date().isoformat(),
        'AssociatedObjectReferenceID': _create_vebsv_id_reference(vebsv_id),
        'AssociatedObjectDocumentScopeReferenceID': scope_refs,
    }
    environmental_data = {'TypeAEvent': type_a_event}
    return _build_environmental_data_instance(TransferMessageType.DROPSHIPPING_DECLARATION.value, listed_data, environmental_data,
                                              "handover")


def create_transport_declaration_message(organisations: List[Organisation], local_units: List[LocalUnit],
                                         shipment_item: ShipmentItem, vebsv_id: str, transport_uuid: str,
                                         transport_mean: TransportMean, planned_waypoints: List[PlannedWaypoint]):
    listed_data = _create_listed_data(organisations, local_units)
    scope_refs_b = [
        _create_scope_reference(ROLE_ID_TRANSPORTEUR, OBJECT_TYPE_NAME_UNTERNEHMEN, 'takeover'),
        _create_scope_reference(ROLE_ID_VERANLASSER, OBJECT_TYPE_NAME_UNTERNEHMEN, 'takeover')
        # TODO: this has to be whoever is transport organizer
    ]
    type_b_event = _create_type_b_event(transport_mean, transport_uuid, scope_refs_b)
    type_c_events = [_create_type_c_event(wp, shipment_item, vebsv_id) for wp in planned_waypoints]
    environmental_data = {'TypeBEvent': type_b_event, 'TypeCEvent': type_c_events}
    return _build_environmental_data_instance(TransferMessageType.TRANSPORT_DECLARATION.value, listed_data, environmental_data,
                                              "takeover")


def create_transport_start_message(organisations: List[Organisation], local_units: List[LocalUnit],
                                   shipment_item: ShipmentItem,
                                   vebsv_id: str, transport_uuid: str, transport_mean: TransportMean,
                                   waypoints: List[PlannedWaypoint], carrier_reference: str):
    listed_data = _create_listed_data(organisations, local_units)
    scope_ref_b = _create_scope_reference(ROLE_ID_TRANSPORTEUR, OBJECT_TYPE_NAME_UNTERNEHMEN, carrier_reference)
    type_b_event = _create_type_b_event(transport_mean, transport_uuid, scope_ref_b)
    type_c_event = _create_type_c_event(waypoints[0], shipment_item, vebsv_id)
    environmental_data = {'TypeBEvent': type_b_event, 'TypeCEvent': type_c_event}
    return _build_environmental_data_instance(TransferMessageType.TRANSPORT_START_DECLARATION.value, listed_data,
                                              environmental_data, carrier_reference)


def create_takeover_message(organisations: List[Organisation], local_units: List[LocalUnit],
                            shipment_item: ShipmentItem,
                            vebsv_id: str):
    listed_data = _create_listed_data(organisations, local_units)
    scope_refs = [
        _create_scope_reference(ROLE_ID_HANDOVER_PARTY, OBJECT_TYPE_NAME_UNTERNEHMEN, 'handover'),
        _create_scope_reference(ROLE_ID_TAKEOVER_PARTY, OBJECT_TYPE_NAME_UNTERNEHMEN, 'takeover'),
        _create_scope_reference(ROLE_ID_DROPOFF_SITE, OBJECT_TYPE_NAME_STANDORT, 'dropoff_site'),
    ]
    type_a_event = _create_type_a_event(shipment_item, vebsv_id, scope_refs)
    environmental_data = {'TypeAEvent': type_a_event}
    return _build_environmental_data_instance(TransferMessageType.TAKEOVER_DECLARATION.value, listed_data, environmental_data,
                                              "takeover")


# --- Helper Functions for payload construction ---

def _create_type_id(collection_id: str, value: str, designation: str = None):
    type_id = {'collectionID': collection_id, '_value_1': value}
    if designation:
        type_id['objectDesignation'] = designation
    return type_id


def _create_scope_reference(role_id: str, object_type_name: str, value: str):
    return {'roleID': role_id, 'objectTypeName': object_type_name, '_value_1': value}


def _create_vebsv_id_reference(vebsv_id: str):
    return {
        'roleID': ROLE_ID_VEBSV_ID,
        'collectionID': COLLECTION_ID_VEBSV_ID,
        'objectDesignation': OBJECT_DESIGNATION_VEBSV_ID,
        '_value_1': vebsv_id,
    }


def _create_listed_data(organisations: List[Organisation], local_units: List[LocalUnit]):
    return {
        'Organization': [org.parse() for org in organisations],
        'LocalUnit': [lu.parse() for lu in local_units],
    }


def _create_type_a_event(shipment_item: ShipmentItem, vebsv_id: str, scope_refs: List[dict]):
    type_a_event = {
        'TypeID': _create_type_id(COLLECTION_ID_EVENT_TYPE_PHYSICAL, TYPE_ID_PHYSICAL_EVENT,
                                  OBJECT_DESIGNATION_PHYSICAL),
        'Date': datetime.now().date().isoformat(),
        'Object': shipment_item.parse_transfer(),
        'AssociatedObjectReferenceID': _create_vebsv_id_reference(vebsv_id),
        'AssociatedObjectDocumentScopeReferenceID': scope_refs,
    }
    return type_a_event


def _create_type_b_event(transport_mean: TransportMean, transport_uuid: str, scope_refs: Union[dict, List[dict]]):
    return {
        'DocumentScopeAssignmentID': 'transport',
        'Object': {
            'PredeterminedScopeAssignmentID': transport_mean.internal_id,
            'TypeID': _create_type_id(COLLECTION_ID_TRANSPORT_MEAN_TYPE, transport_mean.gtin)
        },
        'AssociatedObjectDocumentScopeReferenceID': scope_refs,
        'TransportID': transport_uuid
    }


def _create_type_c_event(waypoint: PlannedWaypoint, shipment_item: ShipmentItem, vebsv_id: str):
    waypoint_type = TYPE_ID_LOADING_WAYPOINT if waypoint.loading_waypoint else TYPE_ID_UNLOADING_WAYPOINT
    return {
        'TypeID': _create_type_id(COLLECTION_ID_WAYPOINT_TYPE, waypoint_type),
        'DateTime': waypoint.period.start_date,
        'Object': shipment_item.parse_transfer(),
        'AssociatedObjectReferenceID': _create_vebsv_id_reference(vebsv_id),
        'AssociatedObjectDocumentScopeReferenceID': [
            _create_scope_reference(ROLE_ID_TRANSPORT_EVENT, OBJECT_TYPE_NAME_EINZELTRANSPORT, 'transport'),
            _create_scope_reference(ROLE_ID_PARTY_IN_TRANSPORT, OBJECT_TYPE_NAME_UNTERNEHMEN,
                                    waypoint.party_internal_id),
            _create_scope_reference(ROLE_ID_LOCATION_IN_TRANSPORT, OBJECT_TYPE_NAME_STANDORT,
                                    waypoint.location_internal_id),
        ],
    }


def _build_environmental_data_instance(document_type_id: str, listed_data: dict, environmental_data_document: dict,
                                       associated_party_ref: str):
    current_date = datetime.now().date().isoformat()
    current_datetime = datetime.now().astimezone().isoformat()
    return {
        'EnvironmentalDataEnvelope': {
            'Document': {
                'CreationDate': current_datetime,
                'ReferenceDataVersionDate': current_date,
                'DocumentEvent': {
                    'TypeID': _create_type_id(COLLECTION_ID_DOCUMENT_CREATION, TYPE_ID_DOCUMENT_CREATION,
                                              OBJECT_DESIGNATION_DOCUMENT_CREATION),
                    'DateTime': current_datetime,
                    'AssociatedObjectDocumentScopeReferenceID': _create_scope_reference(ROLE_ID_DOCUMENT_CREATOR,
                                                                                        OBJECT_TYPE_NAME_UNTERNEHMEN,
                                                                                        associated_party_ref),
                },
            },
            'ListedData': listed_data,
            'EnvironmentalDataDocument': {
                'Document': {
                    'TypeID': _create_type_id(COLLECTION_ID_DOCUMENT_TYPE, document_type_id),
                },
                'EnvironmentalData': environmental_data_document,
            },
        },
    }


def share_document(auth: Auth, transaction_uuid: str, environmental_data_instance: dict):
    session.headers.update({
        'Authorization': auth.transfer_auth_header(transaction_uuid, "ShareDocument"),
    })
    request_data = {
        'InterfaceVersionID': INTERFACE_VERSION,
        'ConnectorVersionID': CONNECTOR_VERSION,
        'TransactionUUID': transaction_uuid,
        'EnvironmentalDataInstance': environmental_data_instance,
    }
    return client.service.ShareDocument(**request_data)

def cancel_document(auth: Auth, transaction_uuid: str, document_uuid: str, reason: WasteRevocationReason):
    session.headers.update({
        'Authorization': auth.transfer_auth_header(transaction_uuid, "CancelDocument"),
    })
    request_data = {
        'InterfaceVersionID': INTERFACE_VERSION,
        'ConnectorVersionID': CONNECTOR_VERSION,
        'TransactionUUID': transaction_uuid,
        'DocumentUUID': document_uuid,
        'ChangeReasonID': {
            'collectionID': '7521',
            '_value_1': reason.gtin
        }
    }
    return client.service.CancelDocument(**request_data)
