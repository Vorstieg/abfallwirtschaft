import uuid

from odoo.addons.abfall_stammdaten.models.core_data.waste_revocation_reason import WasteRevocationReason

from .begleitschein_ws_transfer import (
    request_waste_transfer_id,
    share_document,
    cancel_document,
    create_handover_declaration_message,
    create_transport_declaration_message,
    create_transport_start_message,
    create_takeover_message,
    create_dropship_declaration_message, )
from ..auth import Auth
from ..vebsv_begleitschein import VebsvBegleitscheinLine, VebsvBegleitschein, TransferRequestType


class BegleitscheinTransferService:
    auth: Auth

    def __init__(self, auth):
        self.auth = auth

    def request_vebsv_id(self):
        response = request_waste_transfer_id(self.auth, str(uuid.uuid4()))
        return response.WasteTransferID

    def declare_handover(self, begleitschein: VebsvBegleitschein, begleitschein_line: VebsvBegleitscheinLine):
        transaction_uuid = str(uuid.uuid4())
        message = create_handover_declaration_message(begleitschein.selected_organisations(),
                                                      begleitschein.selected_local_units(dropoff=False),
                                                      begleitschein_line.get_shipment_item(),
                                                      begleitschein_line.vebsv_id)
        share_document(self.auth, transaction_uuid, message)
        begleitschein_line.add_request_identifier(TransferRequestType.HANDOVER_DECLARATION, transaction_uuid)

    def cancel_declare_handover(self, begleitschein_line: VebsvBegleitscheinLine, reason: WasteRevocationReason):
        cancel_document(self.auth, str(uuid.uuid4()),
                        begleitschein_line.get_request_identifier(TransferRequestType.HANDOVER_DECLARATION), reason)

    def declare_dropship(self, begleitschein: VebsvBegleitschein, begleitschein_line: VebsvBegleitscheinLine):
        transaction_uuid = str(uuid.uuid4())
        message = create_dropship_declaration_message(begleitschein.selected_organisations(),
                                                      begleitschein_line.vebsv_id)
        share_document(self.auth, transaction_uuid, message)
        begleitschein_line.add_request_identifier(TransferRequestType.DROPSHIPPING_DECLARATION, transaction_uuid)

    def cancel_declare_dropship(self, begleitschein_line: VebsvBegleitscheinLine, reason: WasteRevocationReason):
        cancel_document(self.auth, str(uuid.uuid4()),
                        begleitschein_line.get_request_identifier(TransferRequestType.DROPSHIPPING_DECLARATION), reason)

    def declare_transport(self, begleitschein_line: VebsvBegleitscheinLine, begleitschein: VebsvBegleitschein):
        transaction_uuid = str(uuid.uuid4())
        message = create_transport_declaration_message(begleitschein.selected_organisations(),
                                                       begleitschein.selected_local_units(),
                                                       begleitschein_line.get_shipment_item(),
                                                       begleitschein_line.vebsv_id,
                                                       begleitschein.transport_uuid,
                                                       begleitschein.transport_mean(),
                                                       begleitschein.selected_waypoints())
        share_document(self.auth, transaction_uuid, message)
        begleitschein_line.add_request_identifier(TransferRequestType.TRANSPORT_DECLARATION, transaction_uuid)

    def cancel_declare_transport(self, begleitschein_line: VebsvBegleitscheinLine, reason: WasteRevocationReason):
        cancel_document(self.auth, str(uuid.uuid4()),
                        begleitschein_line.get_request_identifier(TransferRequestType.TRANSPORT_DECLARATION), reason)

    def start_transport(self, begleitschein_line: VebsvBegleitscheinLine, begleitschein: VebsvBegleitschein):
        transaction_uuid = str(uuid.uuid4())
        message = create_transport_start_message(begleitschein.selected_organisations(),
                                                 begleitschein.selected_local_units(dropoff=False),
                                                 begleitschein_line.get_shipment_item(),
                                                 begleitschein_line.vebsv_id,
                                                 begleitschein.transport_uuid,
                                                 begleitschein.transport_mean(),
                                                 begleitschein.selected_waypoints(dropoff=False),
                                                 begleitschein.carrier_reference())
        share_document(self.auth, transaction_uuid, message)
        begleitschein_line.add_request_identifier(TransferRequestType.TRANSPORT_START_DECLARATION, transaction_uuid)

    def cancel_start_transport(self, begleitschein_line: VebsvBegleitscheinLine, reason: WasteRevocationReason):
        cancel_document(self.auth, str(uuid.uuid4()),
                        begleitschein_line.get_request_identifier(TransferRequestType.TRANSPORT_START_DECLARATION),
                        reason)

    def declare_takeover(self, begleitschein_line: VebsvBegleitscheinLine, begleitschein: VebsvBegleitschein):
        transaction_uuid = str(uuid.uuid4())
        message = create_takeover_message(begleitschein.selected_organisations(), begleitschein.selected_local_units(pickup=False),
                                          begleitschein_line.get_shipment_item(), begleitschein_line.vebsv_id)
        share_document(self.auth, transaction_uuid, message)
        begleitschein_line.add_request_identifier(TransferRequestType.TAKEOVER_DECLARATION, transaction_uuid)

    def cancel_declare_takeover(self, begleitschein_line: VebsvBegleitscheinLine, reason: WasteRevocationReason):
        cancel_document(self.auth, str(uuid.uuid4()),
                        begleitschein_line.get_request_identifier(TransferRequestType.TAKEOVER_DECLARATION), reason)
