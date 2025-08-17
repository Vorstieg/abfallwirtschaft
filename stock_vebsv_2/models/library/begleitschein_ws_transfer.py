from zeep import Client, Settings
from zeep.transports import Transport
import requests
from .auth import Auth
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