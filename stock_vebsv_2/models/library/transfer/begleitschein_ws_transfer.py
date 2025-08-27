from datetime import datetime
from typing import List

from zeep import Client, Settings
from zeep.transports import Transport
import requests
from ..auth import Auth
from ..structure import Organisation, LocalUnit, ShipmentItem

WSDL_URL = "https://edmdemo.umweltbundesamt.at/vebsv-ws/TransferOfWasteService?wsdl"

settings = Settings(strict=False)
session = requests.Session()
transport = Transport(session=session)

client = Client(wsdl=WSDL_URL, settings=settings, transport=transport)


def request_waste_transfer_id(auth: Auth, transaction_uuid):
    session.headers.update({
        'Authorization': auth.transfer_auth_header(transaction_uuid, "RequestWasteTransferID"),
    })
    request_data = {
        'ConnectorVersionID': "1.00",
        'TransactionUUID': transaction_uuid
    }

    return client.service.RequestWasteTransferID(**request_data)


def share_document(auth: Auth, transaction_uuid, organisations: List[Organisation], localUnits: List[LocalUnit],
                   documentTypeId: str , shipmentItem: List[ShipmentItem], vebsv_id:str):
    current_time = datetime.now().isoformat()
    session.headers.update({
        'Authorization': auth.transfer_auth_header(transaction_uuid, "RequestWasteTransferID"),
    })
    request_data = {
        'InterfaceVersionID': '1.00',
        'ConnectorVersionID': 'ebs-api',
        'TransactionUUID': transaction_uuid,
        'EnvironmentalDataInstance': {
            'EnvironmentalDataEnvelope': {
                'Document': {
                    'CreationDate': current_time,
                    'ReferenceDataVersionDate': current_time,
                    'DocumentEvent': {
                        'TypeID': '9008390106594',
                        'DateTime': current_time,
                        'AssociatedObjectDocumentScopeReferenceID': {
                            'roleID': '9008390104583',
                            'objectTypeName': 'Unternehmen',
                            '_value_1': 'handover',
                        },
                    },
                },
                'ListedData': {
                    'Organization': list(map(lambda x: x.parse(), organisations)),
                    'LocalUnit': list(map(lambda x: x.parse(), localUnits)),
                },
                'EnvironmentalDataDocument': {
                    'Document': {
                        'TypeID': {
                            'collectionID': '5064',
                            '_value_1': '9008390116289',
                        },
                    },
                    'EnvironmentalData': {
                        'TypeAEvent': {
                            'TypeID': {
                                'collectionID': '8926',
                                '_value_1': documentTypeId,
                            },
                            'Date': current_time,
                            'Object': list(map(lambda x: x.parse_transfer(), shipmentItem)),
                            'AssociatedObjectReferenceID': {
                                'roleID': '9008390104576',
                                'collectionID': '9008390104026',
                                'objectDesignation': vebsv_id,
                                '_value_1': '889821659734',
                            },
                            'AssociatedObjectDocumentScopeReferenceID': [
                                {
                                    'roleID': '9008390104705',
                                    'roleDesignation': 'Übergeber',
                                    'objectTypeName': 'Unternehmen',
                                    '_value_1': 'handover',
                                },
                                {
                                    'roleID': '9008390104712',
                                    'roleDesignation': 'Übernehmer',
                                    'objectTypeName': 'Unternehmen',
                                    '_value_1': 'takeover',
                                },
                                {
                                    'roleID': '9008390108338',
                                    'roleDesignation': 'Beginnstelle',
                                    'objectTypeName': 'Standort',
                                    '_value_1': 'pickUpLocation',
                                },
                            ],
                        },
                    },
                },
            },
        },
    }

    return client.service.ShareDocument(ShareDocumentRequest=request_data)
