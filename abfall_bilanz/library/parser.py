import os
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Union

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


# =============================================================================
# Address Types
# =============================================================================

@dataclass
class Address:
    """Office address for parties (required for non-registered parties)"""
    country_id: str  # ISO 3166-1 numeric code (e.g., "040" for Austria)
    city_name: Optional[str] = None
    postcode: Optional[str] = None
    street_name: Optional[str] = None
    building_number: Optional[str] = None

    def parse(self):
        result = {'CountryID': self.country_id}
        if self.city_name:
            result['CityName'] = self.city_name
        if self.postcode:
            result['Postcode'] = self.postcode
        if self.street_name:
            result['StreetName'] = self.street_name
        if self.building_number:
            result['BuildingNumber'] = self.building_number
        return result


# =============================================================================
# Party / Location Types
# =============================================================================

@dataclass
class WasteMovementSite:
    """Represents a Site (Standort) or Installation (Anlage) with GLN"""
    id: str  # GLN
    name: str

    def parse(self):
        return {
            'ID': self.id,
            'Name': self.name,
        }


@dataclass
class Party:
    """
    Represents a party in a waste movement.
    
    For registered parties: only id (GLN) and name are required.
    For non-registered parties: business_type_code, name, and office_address are required.
    """
    id: Optional[str] = None  # Person GLN (optional for non-registered)
    name: Optional[str] = None
    business_type_code: Optional[str] = None  # NACE code for non-registered parties
    office_address: Optional[Address] = None
    type_code: Optional[str] = None  # Party type code from Codeliste 6911/6727

    def parse(self):
        result = {}
        
        # ID (GLN) - for registered parties
        if self.id:
            result['ID'] = self.id
            
        # Type code (for summarized reporting by party type)
        if self.type_code:
            result['TypeCode'] = self.type_code
            
        # Business type (NACE code) - required for non-registered parties
        if self.business_type_code:
            result['BusinessTypeCode'] = self.business_type_code
            
        # Organization name
        if self.name:
            result['SpecifiedOrganization'] = {'Name': self.name}
            
        # Office address - required for non-registered parties
        if self.office_address:
            result['OfficeAddress'] = self.office_address.parse()
            
        return result


@dataclass
class SpecifiedLocation:
    """Location specification with site and/or installation"""
    site: Optional[WasteMovementSite] = None
    installation: Optional[WasteMovementSite] = None
    address: Optional[Address] = None  # For locations without registered site/installation

    def parse(self):
        result = {}
        if self.site:
            result['SpecifiedOperatingSite'] = self.site.parse()
        if self.installation:
            result['SpecifiedInstallation'] = self.installation.parse()
        if self.address:
            result['PostalAddress'] = self.address.parse()
        return result


@dataclass
class WasteMovementLocation:
    """Complete location info for waste handover/takeover"""
    party: Party
    location: SpecifiedLocation
    physical_process: str  # GTIN for origin/treatment process type

    def parse_handover(self):
        result = {}
        if self.party:
            result['HandOverParty'] = self.party.parse()
        if self.location:
            location_data = self.location.parse()
            if location_data:
                result['SpecifiedLocation'] = location_data
        if self.physical_process:
            result['OriginPhysicalProcess'] = {'TypeCode': self.physical_process}
        return result

    def parse_takeover(self):
        result = {}
        if self.party:
            result['TakeOverParty'] = self.party.parse()
        if self.location:
            location_data = self.location.parse()
            if location_data:
                result['SpecifiedLocation'] = location_data
        if self.physical_process:
            result['DesignatedTreatmentPhysicalProcess'] = {'TypeCode': self.physical_process}
        return result


# =============================================================================
# Waste Material Movement (Abfallbewegung)
# =============================================================================

@dataclass
class WasteHandlingNotification:
    """A single waste material movement entry"""
    id: str  # Unique movement ID
    type_code: str  # Transport type GTIN from Codeliste 9572
    takeover_party: WasteMovementLocation
    handover_party: WasteMovementLocation
    classification_code: str  # Waste type GTIN from Codeliste 5174
    quantification_type: str  # Quantification type GTIN from Codeliste 7299
    weight: float  # Mass in kg
    movement_start_date: Optional[date] = None
    movement_end_date: Optional[date] = None

    def parse(self):
        result = {
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
        # Add movement period if specified
        if self.movement_start_date:
            result['MovementPeriod'] = {
                'StartDate': self.movement_start_date,
            }
            if self.movement_end_date:
                result['MovementPeriod']['EndDate'] = self.movement_end_date
        return result


# =============================================================================
# Storage State (Lagerstand)
# =============================================================================

@dataclass
class StoredMaterial:
    """Material stored at an installation"""
    classification_code: Optional[str]  # Waste type GTIN (optional for buffer storage)
    quantification_type: str  # Quantification type GTIN
    weight: float  # Mass in kg

    def parse(self):
        result = {
            'MassMeasurement': {
                'QuantificationTypeCode': self.quantification_type,
                'DeterminedMeasure': {
                    'unitCode': 'KGM',
                    '_value_1': self.weight,
                }
            }
        }
        if self.classification_code:
            result['ClassificationCode'] = self.classification_code
        return result


@dataclass
class StorageState:
    """
    Storage state at an installation at a specific date.
    Required at start and end of reporting period.
    """
    installation_id: str  # Installation GLN
    reporting_date: date  # Date of the storage state
    stored_material: StoredMaterial
    buffer_type_code: Optional[str] = None  # For buffer storage (Pufferlager)

    def parse(self):
        result = {
            'ID': self.installation_id,
            'ReportingDate': self.reporting_date,
            'StoredMaterial': self.stored_material.parse(),
        }
        if self.buffer_type_code:
            result['BufferTypeCode'] = self.buffer_type_code
        return result


# =============================================================================
# Storage Correction (Lagerstandskorrektur)
# =============================================================================

@dataclass
class CorrectionMaterial:
    """Material added or removed as correction"""
    classification_code: str  # Waste type GTIN
    quantification_type: str  # Quantification type GTIN
    weight: float  # Mass in kg

    def parse(self):
        return {
            'ClassificationCode': self.classification_code,
            'MassMeasurement': {
                'QuantificationTypeCode': self.quantification_type,
                'DeterminedMeasure': {
                    'unitCode': 'KGM',
                    '_value_1': self.weight,
                }
            }
        }


@dataclass
class StorageCorrection:
    """Storage state correction at an installation"""
    installation_id: str  # Installation GLN
    reporting_date: date  # Date of correction
    added_material: Optional[CorrectionMaterial] = None  # Material added
    removed_material: Optional[CorrectionMaterial] = None  # Material removed

    def parse(self):
        result = {
            'ID': self.installation_id,
            'ReportingDate': self.reporting_date,
        }
        if self.added_material:
            result['AddedMaterial'] = self.added_material.parse()
        if self.removed_material:
            result['RemovedMaterial'] = self.removed_material.parse()
        return result


# =============================================================================
# Waste Reclassification (Abfallartenneuzuordnung)
# =============================================================================

@dataclass
class WasteReclassification:
    """
    Waste type reclassification record.
    Used when waste is reclassified from one type to another.
    """
    installation_id: str  # Installation GLN where reclassification occurred
    preliminary_classification_code: str  # Original waste type GTIN
    classification_code: str  # New waste type GTIN
    quantification_type: str  # Quantification type GTIN
    weight: float  # Mass in kg
    reclassification_reason_type_code: Optional[str] = None  # Reason code from Codeliste 3327
    reporting_date: Optional[date] = None

    def parse(self):
        result = {
            'PreliminaryClassificationCode': self.preliminary_classification_code,
            'ClassificationCode': self.classification_code,
            'MassMeasurement': {
                'QuantificationTypeCode': self.quantification_type,
                'DeterminedMeasure': {
                    'unitCode': 'KGM',
                    '_value_1': self.weight,
                }
            },
            'SpecifiedLocation': {
                'SpecifiedInstallation': {
                    'ID': self.installation_id,
                }
            }
        }
        if self.reclassification_reason_type_code:
            result['ReclassificationReasonTypeCode'] = self.reclassification_reason_type_code
        if self.reporting_date:
            result['ReportingDate'] = self.reporting_date
        return result


# =============================================================================
# Remaining Capacity (Deponierestkapazität)
# =============================================================================

@dataclass
class RemainingCapacity:
    """Remaining capacity for landfills"""
    installation_id: str  # Installation GLN
    reporting_date: date
    approved_remaining_capacity: Optional[float] = None  # in m³
    physical_remaining_capacity: Optional[float] = None  # in m³

    def parse(self):
        result = {
            'ID': self.installation_id,
            'ReportingDate': self.reporting_date,
        }
        if self.approved_remaining_capacity is not None:
            result['ApprovedRemainingCapacityMeasure'] = {
                'unitCode': 'MTQ',
                '_value_1': self.approved_remaining_capacity,
            }
        if self.physical_remaining_capacity is not None:
            result['PhysicalRemainingCapacityMeasure'] = {
                'unitCode': 'MTQ',
                '_value_1': self.physical_remaining_capacity,
            }
        return result


# =============================================================================
# Type alias for all entry types
# =============================================================================

NotificationEntry = Union[
    WasteHandlingNotification,
    StorageState,
    StorageCorrection,
    WasteReclassification,
    RemainingCapacity
]


# =============================================================================
# XML Generation
# =============================================================================

def create_waste_handling_notification_xml(
    start_date: date, 
    end_date: date, 
    obligated_party: str, 
    waste_movements: List[WasteHandlingNotification],
    storage_states: Optional[List[StorageState]] = None,
    storage_corrections: Optional[List[StorageCorrection]] = None,
    waste_reclassifications: Optional[List[WasteReclassification]] = None,
    remaining_capacities: Optional[List[RemainingCapacity]] = None,
    is_empty_report: bool = False
) -> str:
    """
    Creates the XML for a Waste Handling Notification (Abfallbilanz).
    
    Args:
        start_date: Start of current period
        end_date: End of current period
        obligated_party: Person GLN of the obligated party (meldepflichtiges Unternehmen)
        waste_movements: List of waste movements (Abfallbewegungen)
        storage_states: List of storage states at start/end of period (Lagerstände)
        storage_corrections: List of storage corrections (Lagerstandskorrekturen)
        waste_reclassifications: List of waste reclassifications (Abfallartenneuzuordnungen)
        remaining_capacities: List of remaining landfill capacities (Deponierestkapazitäten)
        is_empty_report: If True, generates a 'Leermeldung' (Empty Report)
    
    Returns:
        XML string conforming to BALANCE v2.15 schema
    """
    with open(f'{base_path}/waste_balance_message.xsd', 'rb') as xsd_file:
        xmlschema_doc = load_external(xsd_file, Transport())
    schema = Schema(xmlschema_doc)
    WasteHandlingNotificationType = schema.get_element("ns0:WasteHandlingNotification")

    # GTINs for Meldungsarten from Codeliste 1848
    NOTIFICATION_TYPE_JAHRESABFALLBILANZ = "9008390100400"
    NOTIFICATION_TYPE_LEERMELDUNG = "9008390121726"

    notification_type = NOTIFICATION_TYPE_LEERMELDUNG if is_empty_report else NOTIFICATION_TYPE_JAHRESABFALLBILANZ

    # Build the list of SpecifiedWasteHandlingNotificationEntry elements
    # (Empty for Leermeldung)
    notification_entries = []
    
    if not is_empty_report:
        # Add waste movements
        for movement in waste_movements:
            notification_entries.append({'WasteMaterialMovement': movement.parse()})
        
        # Add storage states
        if storage_states:
            for state in storage_states:
                notification_entries.append({'StorageStateInstallation': state.parse()})
        
        # Add storage corrections
        if storage_corrections:
            for correction in storage_corrections:
                notification_entries.append({'StorageCorrectionInstallation': correction.parse()})
        
        # Add waste reclassifications
        if waste_reclassifications:
            for reclassification in waste_reclassifications:
                notification_entries.append({'WasteReclassificationMaterial': reclassification.parse()})
        
        # Add remaining capacities
        if remaining_capacities:
            for capacity in remaining_capacities:
                notification_entries.append({'RemainingCapacityInstallation': capacity.parse()})

    notification_data = {
        'CreationSoftwareInterfaceVersionID': SOFTWARE_INTERFACE_VERSION,
        'CreationSoftwareVersionID': SOFTWARE_VERSION,
        'CreationSoftwareName': SOFTWARE_NAME,
        'SpecifiedNotification': {
            'TypeCode': notification_type,
            'ObligatedParty': {
                'ID': obligated_party,
            },
            'CoveredPeriod': {
                'StartDate': start_date,
                'EndDate': end_date,
            }
        }
    }

    # Only include entries if it's NOT an empty report
    if not is_empty_report:
        notification_data['SpecifiedSinglePeriodWasteHandlingNotification'] = {
            'SpecifiedWasteHandlingNotificationEntry': notification_entries
        }

    waste_notification_xml_element = WasteHandlingNotificationType(**notification_data)
    body = E.WasteHandlingNotification()
    WasteHandlingNotificationType.render(body, waste_notification_xml_element)
    return etree.tostring(body[0]).decode('utf-8')
