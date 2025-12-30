import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List


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

    def parse_transfer(self):
        return {
            'PropertyKindID': {
                # Transfer and message WS use different reference tables for PropertyKindID. The message WS uses 9000 while the transfer WS uses 5618.
                # The 5618 table currently has only one entry, which is masse.
                'collectionID': '5618',
                'objectDesignation': 'Masse',
                '_value_1': '9008390104439',
            },
            'ValueAssignmentStatement': {
                'NumericValue': {
                    'unitID': 'kg',
                    '_value_1': self.mass_in_kg,
                },
            },
            # the Transfer and Message WS call the quantification type different names. However, they use the same reference table.
            'MethodID': {
                'collectionID': '7299',
                '_value_1': self.quantification_type_id,
            }}


@dataclass()
# This is called ShipmentItem in the message WS. In the transfer WS it is called Object
class ShipmentItem:
    shipment_item_uuid: uuid.UUID
    line_item_number: int
    waste_type_gtin: str
    waste_contamination_id: str
    waste_type_description: str
    vebsv_id: str
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
            **({'WasteContaminationTypeID': {
                'collectionID': '7835',
                '_value_1': self.waste_contamination_id
            }} if self.waste_contamination_id else {}),
            'NetPropertyStatement': self.netProperty.parse(),
            **({'ConsignmentNoteReferenceID': self.vebsv_id} if self.vebsv_id else {}),
            **({'DangerousGoodsDescription': {
                'Description': {
                    'IndividualDescription': {
                        'languageID': 'de',
                        '_value_1': self.waste_type_description
                    }}
            }} if self.waste_type_description and self.waste_contamination_id else {}),
            'ContainsPersistentOrganicPollutant': self.contains_pop
        }

    def parse_message_transport(self):
        return {
            'DocumentScopeAssignmentID': 'shipment_item_' + str(self.line_item_number),
            'UUID': self.shipment_item_uuid,
        }

    def parse_message_transport_item(self):
        return {
            'ShipmentItemReferenceID': 'shipment_item_' + str(self.line_item_number),
            'WasteTypeID': {
                'collectionID': '5174',
                '_value_1': self.waste_type_gtin
            },
            'NetPropertyStatement': self.netProperty.parse(),
            # 'ConsignmentNoteReferenceID': '',
            'DangerousGoodsDescription': dangerous_goods_description(self.waste_type_description),
            'ContainsPersistentOrganicPollutant': self.contains_pop
        }

    def parse_transfer(self):
        return {
            'TypeID': {
                'collectionID': '5174',
                '_value_1': self.waste_type_gtin,
            },
            'Description': {
                'IndividualDescription': {
                    'languageID': 'de',
                    '_value_1': self.waste_type_description,
                },
            },
            'PropertyStatement': self.netProperty.parse_transfer(),
            'ContainsPersistentOrganicPollutant': self.contains_pop,
        }


@dataclass()
class Period:
    start_date: datetime
    end_date: datetime

    def parse(self):
        return {
            'StartDate': self.start_date.date().isoformat(),
            'EndDate': self.end_date.date().isoformat(),
            'StartTime': self.start_date.time().isoformat(),
            'EndTime': self.end_date.time().isoformat(),
        }


@dataclass()
class PlannedWaypoint:
    period: Period
    location_internal_id: str
    party_internal_id: str
    loading_waypoint: bool = False
    transshipment_waypoint: bool = False

    def parse(self):
        return {
            'Period': self.period.parse(),
            'SiteLocalUnitReferenceID': self.location_internal_id,
            'PartyReferenceID': self.party_internal_id,
            'LoadingWaypoint': self.loading_waypoint,
            'TransshipmentWaypoint': self.transshipment_waypoint,
        }

    def parse_pick_up_service(self):
        return {
            'PickUpSiteService': {
                'Period': self.period.parse(),
                'SiteLocalUnitReferenceID': self.location_internal_id,
                'PartyReferenceID': self.party_internal_id,
            }}

    def parse_drop_of_service(self):
        return {
            'DropOffSiteService': {
                'Period': self.period.parse(),
                'SiteLocalUnitReferenceID': self.location_internal_id,
                'PartyReferenceID': self.party_internal_id,
            }}


@dataclass()
class Shipment:
    shipment_uuid: uuid.UUID
    internal_id: str
    shipment_items: List[ShipmentItem]
    pickup_site_service: PlannedWaypoint
    drop_of_site_service: PlannedWaypoint

    def parse(self, sms_solution):
        return {
            'UUID': self.shipment_uuid,
            'PredeterminedScopeAssignmentID': self.internal_id,
            'ShipmentItem': list(map(lambda x: x.parse(), self.shipment_items)),
            **(self.pickup_site_service.parse_pick_up_service() if sms_solution else {}),
            **(self.pickup_site_service.parse_drop_of_service() if sms_solution else {}),
            'HandOverPartyReferenceID': "handover",
            'TakeOverPartyReferenceID': "takeover",
        }

    def parse_message_uebernahme(self):
        return {
            'UUID': self.shipment_uuid,
            'PredeterminedScopeAssignmentID': self.internal_id,
            'ShipmentItem': [list(map(lambda x: x.parse(), self.shipment_items))]
        }

    def parse_message_transport(self):
        return {
            'UUID': self.shipment_uuid,
            'DocumentScopeAssignmentID': self.internal_id,
            'ShipmentItem': list(map(lambda x: x.parse_message_transport(), self.shipment_items))
        }


@dataclass()
class TransportMean:
    internal_id: str
    gtin: str

    def parse(self):
        return {
            'PredeterminedScopeAssignmentID': {
                '_value_1': self.internal_id,
            },
            'ModeID': {
                'collectionID': '2939',
                '_value_1': self.gtin,
            },
        }


@dataclass()
class Recipient:
    gln: str
    sms_telephone_number: str = False

    def parse(self):
        return {
            'RecipientID': self.gln,
            'TransactionPurposeCategoryID': {
                'collectionID': '2976',
                '_value_1': 'request'  # two possible values: request and inform
            },
            **({
                   'TelephoneCommunicationNetworkEndpointID': self.sms_telephone_number} if self.sms_telephone_number else {}),
        }
