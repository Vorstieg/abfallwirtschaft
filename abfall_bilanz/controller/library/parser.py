import os
from dataclasses import dataclass
from datetime import date
from typing import List

from lxml import etree
from lxml.builder import ElementMaker
from zeep import Transport
from zeep.loader import load_external
from zeep.xsd import Schema

SOFTWARE_NAME = "Vorstieg"
SOFTWARE_VERSION = "1.0"
SOFTWARE_INTERFACE_VERSION = "2.15"
schema_location = "http://edm.gv.at/schema/WasteBalanceInterfaceV2 ../waste_balance_core_message.xsd"
base_path = os.path.dirname(os.path.abspath(__file__))

E = ElementMaker(
    nsmap={
        'ebil': "http://edm.gv.at/schema/WasteBalanceInterfaceV2",
        'xsi': "http://www.w3.org/2001/XMLSchema-instance"
    }
)


@dataclass
class WasteMovementSite():
    id: str
    name: str

    def parse(self):
        return {
            'ID': self.id,
            'Name': self.name,
        }


@dataclass()
class Party():
    id: str
    name: str

    def parse(self):
        return {
            'ID': self.id,
            'SpecifiedOrganization': {
                'Name': self.name,
            }
        }


@dataclass
class SpecifiedLocation():
    site: WasteMovementSite
    installation: WasteMovementSite

    def parse(self):
        return {
            **({'SpecifiedOperatingSite': self.site.parse()} if self.site else {}),
            **({'SpecifiedInstallation': self.installation.parse()} if self.installation else {}),
        }


@dataclass
class WasteMovementLocation():
    party: Party
    location: SpecifiedLocation
    physical_process: str

    def parse_handover(self):
        return {
            'HandOverParty': self.party.parse(),
            'SpecifiedLocation': self.location.parse(),
            'OriginPhysicalProcess': {
                'TypeCode': self.physical_process,
            }
        }

    def parse_takeover(self):
        return {
            'TakeOverParty': self.party.parse(),
            'SpecifiedLocation': self.location.parse(),
            'DesignatedTreatmentPhysicalProcess': {
                'TypeCode': self.physical_process,
            }
        }


@dataclass
class WasteHandlingNotification():
    id: str
    type_code: str
    takeover_party: WasteMovementLocation
    handover_party: WasteMovementLocation
    classification_code: str
    quantification_type: str
    weight: float

    def parse(self):
        return {
            'ID': self.id,
            'TypeCode': self.type_code,
            'WasteHandOverMovedMaterial': self.handover_party.parse_handover(),
            'WasteTakeOverMovedMaterial': self.takeover_party.parse_takeover(),
            'MovedMaterial': {
                'ClassificationCode': self.classification_code,
                'MassMeasurement': {
                    'QuantificationTypeCode': self.quantification_type,
                    'DeterminedMeasure': {
                        'unitCode': 'KGM',
                        '_value_1': self.weight,
                    }
                }
            }
        }


def create_waste_handling_notification_xml(start_date: date, end_date: date, obligated_party: str,
                                           waste_movements: List[WasteHandlingNotification]):
    with open(f'{base_path}/waste_balance_message.xsd', 'rb') as xsd_file:
        xmlschema_doc = load_external(xsd_file, Transport())
    schema = Schema(xmlschema_doc)
    WasteHandlingNotificationType = schema.get_element("ns0:WasteHandlingNotification")

    waste_notification_xml_element = WasteHandlingNotificationType(**{
        'CreationSoftwareInterfaceVersionID': SOFTWARE_INTERFACE_VERSION,
        'CreationSoftwareVersionID': SOFTWARE_VERSION,
        'CreationSoftwareName': SOFTWARE_NAME,
        'SpecifiedNotification': {
            'TypeCode': "JAB",
            'ObligatedParty': obligated_party,
            'CoveredPeriod': {
                'StartDate': start_date,
                'EndDate': end_date,
            }
        },
        'SpecifiedSinglePeriodWasteHandlingNotification': {
            'SpecifiedWasteHandlingNotificationEntry': {
                'WasteMaterialMovement': [notification.parse() for notification in waste_movements]
            }
        }
    })
    body = E.WasteHandlingNotification()
    WasteHandlingNotificationType.render(body, waste_notification_xml_element)
    return etree.tostring(body[0]).decode('utf-8')
