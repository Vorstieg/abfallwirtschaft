import hmac
import hashlib
import base64

class Auth:
    edm_user: str
    edm_key: str
    connection_id: str
    connection_key: str

    def __init__(self, edm_user, edm_key, connection_id, connection_key):
        self.edm_user = edm_user
        self.edm_key = edm_key
        self.connection_id = connection_id
        self.connection_key = connection_key

    def _user_key_base64(self):
        return base64.b64decode(self.edm_key)

    def _connector_key_base64(self):
        return base64.b64decode(self.connection_key)

    def user_hmac(self, transaction_uuid):
        hashed_user_key = hashlib.sha256(self._user_key_base64()).digest()
        user_string = f"{transaction_uuid}".encode('utf-8')
        return base64.b64encode(hmac.new(hashed_user_key, user_string, hashlib.sha256).digest()).decode('utf-8')

    def connector_hmac(self, transaction_uuid, transaction_string):
        connector_string = f"{transaction_uuid}\n{transaction_string}".encode('utf-8')
        return base64.b64encode(
            hmac.new(self._connector_key_base64(), connector_string, hashlib.sha256).digest()).decode('utf-8')

    def auth_header(self, transaction_uuid, transaction_string):
        return (
            f'EDM0 connectorID="{self.connection_id}",'
            f'connectorHMAC="{self.connector_hmac(transaction_uuid, transaction_string)}",'
            f'dbUUID="{transaction_uuid}",'
            f'userID="{self.edm_user}",'
            f'userHMAC="{self.user_hmac(transaction_uuid)}"'
        )