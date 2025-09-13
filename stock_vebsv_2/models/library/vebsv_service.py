from .message.begleitschein_message_service import BegleitscheinMessageService
from .transfer.begleitschein_transfer_service import BegleitscheinTransferService
from .vebsv_begleitschein import VebsvBegleitschein, VebsvPartner


class VEBSVService():
    message_service: BegleitscheinMessageService
    transfer_service: BegleitscheinTransferService

    def __init__(self, auth):
        self.message_service = BegleitscheinMessageService(auth)
        self.transfer_service = BegleitscheinTransferService(auth)

    def confirm_begleitschein(self, begleitschein: VebsvBegleitschein):
        for begleitschein_line in begleitschein.begleitschein_lines:
            if begleitschein_line.requires_reporting():
                self.transfer_service.declare_handover(
                    begleitschein.selected_organisations(),
                    begleitschein.selected_local_units(),
                    begleitschein_line.get_shipment_item(),
                    begleitschein_line.vebsv_id)
        self.state = 'confirmed'

    def start_begleitschein(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, sms_telephone_number: str):
        has_dangerous_waste = False
        for line in begleitschein.begleitschein_lines:
            if line.requires_reporting():
                has_dangerous_waste = True
                line.vebsv_id = self.transfer_service.request_vebsv_id()

        self.message_service.create_begleitschein(begleitschein, sender, sms_telephone_number)
        return has_dangerous_waste

    def start_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, message_name):
        self.message_service.start_transport(begleitschein, sender, message_name)

        for begleitschein_line in begleitschein.begleitschein_lines:
            if begleitschein_line.requires_reporting():
                self.transfer_service.declare_transport(
                    begleitschein.selected_organisations(),
                    begleitschein.selected_local_units(),
                    begleitschein_line.get_shipment_item(),
                    begleitschein_line.vebsv_id,
                    begleitschein.transport_uuid,
                    begleitschein.transport_mean(),
                    begleitschein.selected_waypoints())
                if begleitschein.dropship_partner_id:
                    self.transfer_service.declare_dropship(
                        begleitschein.selected_organisations(),
                        begleitschein_line.vebsv_id)

    def end_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner):
        self.message_service.end_transport(begleitschein, sender)

        if sender.is_target(begleitschein):
            for begleitschein_line in begleitschein.begleitschein_lines:
                if begleitschein_line.requires_reporting():
                    self.transfer_service.declare_takeover(
                        begleitschein.selected_organisations(),
                        begleitschein.selected_local_units(),
                        begleitschein_line.get_shipment_item(),
                        begleitschein_line.vebsv_id)
