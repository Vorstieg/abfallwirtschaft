import uuid

from .begleitschein_ws_transfer import (
    request_waste_transfer_id,
    share_document,
    create_handover_declaration_message,
    create_transport_declaration_message,
    create_transport_start_message,
    create_takeover_message,
)
from ..auth import Auth
from typing import List
from ..mappings import Organisation, LocalUnit, ShipmentItem, TransportMean, PlannedWaypoint


class BegleitscheinTransferService:
    auth: Auth

    def __init__(self, auth):
        self.auth = auth

    def request_vebsv_id(self):
        response = request_waste_transfer_id(self.auth, uuid.uuid4())
        return response.WasteTransferID

    def declare_begleitschein(self, organisations: List[Organisation], local_units: List[LocalUnit],
                              shipment_item: ShipmentItem, vebsv_id: str):
        message = create_handover_declaration_message(organisations, local_units, shipment_item, vebsv_id)
        share_document(self.auth, uuid.uuid4(), message)

    def declare_transport(self, organisations: List[Organisation], local_units: List[LocalUnit],
                          shipment_item: ShipmentItem, vebsv_id: str, transport_uuid: str, transport_mean: TransportMean,
                          planned_waypoints: List[PlannedWaypoint]):
        message = create_transport_declaration_message(organisations, local_units, shipment_item, vebsv_id,
                                                       transport_uuid, transport_mean, planned_waypoints)
        share_document(self.auth, uuid.uuid4(), message)

        starting_waypoint = planned_waypoints[0]
        local_unit = local_units[0]
        message = create_transport_start_message(organisations, local_unit, shipment_item, vebsv_id, transport_uuid,
                                                 transport_mean, starting_waypoint)
        share_document(self.auth, uuid.uuid4(), message)

    def declare_takeover(self, organisations: List[Organisation], local_units: List[LocalUnit],
                         shipment_item: ShipmentItem, vebsv_id: str, reason: str = None):
        message = create_takeover_message(organisations, local_units, shipment_item, vebsv_id, reason)
        share_document(self.auth, uuid.uuid4(), message)
