import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass()
class Organisation:
    gln: str
    role: str

    def parse(self):
        return {
            'DocumentScopeAssignmentID': self.role,
            'ID': {
                'collectionID': '9008390104026',
                '_value_1': self.gln
            }
        }


@dataclass()
class LocalUnit:
    internal_id: str
    location_gln: str
    location_type: str

    def parse(self):
        return {
            'LocalUnit': {
                'DocumentScopeAssignmentID': self.internal_id,
                'ID': {
                    'collectionID': '9008390104026',
                    '_value_1': self.location_gln,
                },
                'TypeID': {
                    'collectionID': '9351',
                    '_value_1': self.location_type,
                }
            }
        }


@dataclass()
class NetProperty:
    property_kind_id: str
    mass_in_kg: float
    quantification_type_id: str

    def parse(self):
        return {
            'PropertyKindID': {  # (=Type of measurement (mass, volume, etc.)
                'collectionID': '9000',
                '_value_1': self.property_kind_id  # (=Mass of shipment)
            },
            'ValueAssignmentStatement': {
                'NumericValue': {
                    'unitID': 'kg',
                    '_value_1': self.mass_in_kg
                }
            },
            'QuantificationTypeID': {  # (=how measurement got taken)
                'collectionID': '7299',  # https://edm.gv.at/edm_portal/redaList.do?seqCode=euaipzmuqca7vk
                '_value_1': self.quantification_type_id  # (= Estimation)
            }
        }


@dataclass()
class ShipmentItem:
    shipment_item_uuid: uuid.UUID
    line_item_number: int
    waste_type_gtin: str
    waste_contamination_id: str
    waste_type_description: str
    contains_pop: bool
    netProperty: NetProperty

    def parse(self):
        return {
            'UUID': self.shipment_item_uuid,
            'LineItemNumber': self.line_item_number,
            'WasteTypeID': {
                'collectionID': '5174',
                '_value_1': self.waste_type_gtin
            },
            # 'PredeterminedScopeAssignmentID':              # optional, only used when there is no Schlüsselnummer for the waste
            # 'WasteContaminationTypeID': {
            #     'collectionID': '7835',
            #     '_value_1': self.waste_contamination_id  # Optional Spez 77
            # },
            'NetPropertyStatement': self.netProperty.parse(),
            # 'ConsignmentNoteReferenceID' : ''              # ID from first call, not relevant if no "meldepflichtige Abälle"
            'DangerousGoodsDescription': dangerous_goods_description(self.waste_type_description),  # ADR information
            'ContainsPersistentOrganicPollutant': self.contains_pop
        }


@dataclass()
class Shipment:
    shipment_uuid: uuid.UUID
    internal_id: str
    shipment_items: List[ShipmentItem]

    def parse(self):
        return {
            'UUID': self.shipment_uuid,
            'PredeterminedScopeAssignmentID': self.internal_id,
            'ShipmentItem': [list(map(lambda x: x.parse(), self.shipment_items))],
            'HandOverPartyReferenceID': "handover",
            'TakeOverPartyReferenceID': "takeover",
        }


@dataclass()
class PlannedWaypoint:
    start_date: datetime
    end_date: datetime
    location_internal_id: str
    party_internal_id: str
    loading_waypoint: bool
    transshipment_waypoint: bool

    def parse(self):
        return {
            'PlannedWaypointEvent': {
                'Period': {
                    'StartDate': self.start_date.date().isoformat(),
                    'EndDate': self.end_date.date().isoformat(),
                    'StartTime': self.start_date.time().isoformat(),
                    'EndTime': self.end_date.time().isoformat(),
                },
                'SiteLocalUnitReferenceID': self.location_internal_id,
                'PartyReferenceID': self.party_internal_id,
                'LoadingWaypoint': self.loading_waypoint,
                'TransshipmentWaypoint': self.transshipment_waypoint,
            }
        }


@dataclass()
class TransportItem:
    waste_type_gtin: str
    dangerous_waste_description: str
    contains_pop: bool
    netProperty: NetProperty

    def parse(self):
        return {
            'TransportItem': {
                'ShipmentItemReferenceID': 'shipment_item_1',
                'WasteTypeID': {
                    'collectionID': '5174',
                    '_value_1': self.waste_type_gtin
                },
                'NetPropertyStatement': self.netProperty.parse(),
                # 'ConsignmentNoteReferenceID': '',
                'DangerousGoodsDescription': dangerous_goods_description(self.dangerous_waste_description),
                'ContainsPersistentOrganicPollutant': self.contains_pop
            }
        }


def dangerous_goods_description(dangerous_waste_description):
    return {
        'Description': {
            'IndividualDescription': {
                "_value_1": dangerous_waste_description,
                "languageID": "de"
            }
        }
    }


@dataclass()
class TransportMean:
    internal_id: str
    gtin: str

    def parse(self):
        return {
            'PredeterminedScopeAssignmentID': self.internal_id,
            'ModeID': {
                'collectionID': '2939',
                '_value_1': self.gtin,
            },
        },