import logging
from zeep import Client, Transport
from requests import Session
from requests.auth import HTTPBasicAuth

_logger = logging.getLogger(__name__)

class ErasClient:
    def __init__(self, user, password, base_url=None):
        self.user = user
        self.password = password
        self.base_url = base_url
        self.client = self._get_client()

    def _get_client(self):
        session = Session()
        session.auth = HTTPBasicAuth(self.user, self.password)
        transport = Transport(session=session)
        try:
            return Client(self.base_url, transport=transport)
        except Exception as e:
            _logger.error(f"Failed to initialize eRAS client: {e}")
            raise

    def query_register(self, search_params):
        """
        Query the eRAS register.
        :param search_params: Dictionary of search parameters (e.g., {'gln': '...', 'firmenbuchnummer': '...'})
        :return: Response object or None
        """
        if not self.client:
            return None
        
        try:
            # The WSDL defines queryRegisterabfrage taking parameters directly or as a complex type.
            # Based on PDF, it seems to be a wrapper. Let's try passing kwargs.
            # Fix: includeMitinhaber and includeStillgelegte are mandatory
            if 'includeMitinhaber' not in search_params:
                search_params['includeMitinhaber'] = False
            if 'includeStillgelegte' not in search_params:
                search_params['includeStillgelegte'] = False
                
            response = self.client.service.queryRegisterabfrage(**search_params)
            return response
        except Exception as e:
            _logger.error(f"eRAS query failed: {e}")
            raise
