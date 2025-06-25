from requests.auth import HTTPBasicAuth  # or HTTPDigestAuth, or OAuth1, etc.
from requests import Session
from zeep import Client, Settings
from zeep.transports import Transport
from zeep.exceptions import Fault
import datetime


# Configure logging for Zeep (optional, for debugging)
# logging.basicConfig(level=logging.DEBUG)
# logging.getLogger('zeep.transports').setLevel(logging.DEBUG)

WSDL_FILE = 'https://secure.umweltbundesamt.at/ebsws/DeliveryService?wsdl'

settings = Settings(strict=False, xml_huge_tree=True)
session = Session()
session.auth = HTTPBasicAuth("test", "test")

delivery_client = Client(WSDL_FILE, settings=settings, service_name='DeliveryService')

def create_consignment(notifier_gln, consignment_data):
    try:
        consignment_date = datetime.date(2025, 6, 25)  # Current date is June 25, 2025

        # Construct the nested request payload
        consignment_notification_data = {
            'NotifierPartyID': 'AT0000000',  # Replace with your actual Notifier ID (e.g., your EDM party ID)
            'SpecifiedConsignmentNote': [
                {
                    'ConsignmentNoteStatusCode': 'Registered',  # Common status, check valid values
                    'HandOverPartyRemark': 'Test consignment from Zeep client',  # Using general comment
                    'WasteTransportMaterialMovement': {
                        'MovementPeriod': {
                            'EndDateTime': consignment_date,  # Date of the consignment
                        },
                        'PreliminaryCargoMaterial': {
                            'ClassificationCode': '170405',  # Example: Waste code for iron and steel
                            'MassQualifiedMeasurement': {
                                'MeasurementMeasure': 1000.0,  # Example: 1000 kg
                                'MeasurementMethodCode': 'WEIGHED',  # Common method
                            }
                        },
                        'LoadingLocation': {
                            'PostalAddress': {
                                'CityName': 'Wien',
                                'PostcodeCode': '1010',
                                'StreetName': 'Some Street 1',
                                'CountryID': 'AT',
                            }
                        },
                        'UnloadingLocation': {
                            'PostalAddress': {
                                'CityName': 'Graz',
                                'PostcodeCode': '8010',
                                'StreetName': 'Another Road 5',
                                'CountryID': 'AT',
                            }
                        },
                        'EffectiveTransfer': {
                            'HandOverParty': {
                                'SpecifiedOrganization': {
                                    'Name': 'Handover Company GmbH',
                                    'PostalAddress': {
                                        'CityName': 'Wien',
                                        'PostcodeCode': '1010',
                                        'StreetName': 'Handover Street 10',
                                        'CountryID': 'AT'
                                    }
                                }
                            },
                            'TakeOverParty': {
                                'SpecifiedOrganization': {
                                    'Name': 'Takeover Waste Inc',
                                    'PostalAddress': {
                                        'CityName': 'Graz',
                                        'PostcodeCode': '8010',
                                        'StreetName': 'Takeover Road 20',
                                        'CountryID': 'AT'
                                    }
                                }
                            }
                        },
                        'SubordinateMaterialMovement': [  # This is for transport details
                            {
                                'TransportModeCode': 'ROAD',  # 'ROAD', 'RAIL', 'SEA', 'AIR', 'INLAND_WATERWAY'
                                'TransportMeansID': 'W-12345AB',  # e.g., vehicle license plate
                                'CarrierParty': {
                                    'SpecifiedOrganization': {
                                        'Name': 'Transport Co',
                                        'PostalAddress': {
                                            'CityName': 'Linz',
                                            'PostcodeCode': '4020',
                                            'StreetName': 'Logistics Way 30',
                                            'CountryID': 'AT'
                                        }
                                    }
                                }
                            }
                        ],
                    }
                }
            ]
        }
        response = delivery_client.service.StoreEBSConsignment(
            EBSConsignmentNoteNotification=consignment_notification_data)
    except Fault as e:
        print(f"\nSOAP Fault during StoreEBSConsignment call: {e}")
        # print(f"Fault Code: {e.code}")
        # print(f"Fault Reason: {e.message}")
        # if hasattr(e, 'detail'):
        #     print(f"Fault Detail: {e.detail}")
