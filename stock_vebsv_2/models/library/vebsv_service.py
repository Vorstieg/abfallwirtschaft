from .vebsv_begleitschein import VebsvBegleitschein
from .mappings import LocalUnit, TransportMean
from .message.begleitschein_message_service import BegleitscheinMessageService
from .transfer.begleitschein_transfer_service import BegleitscheinTransferService

class VEBSVService():
    message_service: BegleitscheinMessageService
    transfer_service: BegleitscheinTransferService

    def __init__(self, auth):
        self.message_service = BegleitscheinMessageService(auth)
        self.transfer_service = BegleitscheinTransferService(auth)

    def declare_begleitschein(self, begleitschein: VebsvBegleitschein):
        for begleitschein_line in begleitschein.begleitschein_lines:
            if begleitschein_line.requires_reporting():
                self.transfer_service.declare_handover(
                    begleitschein.selected_organisations(),
                    begleitschein.selected_local_units(),
                    begleitschein_line.get_shipment_item(),
                    begleitschein_line.vebsv_id)
        self.state = 'confirmed'

    def start_begleitschein(self, begleitschein: VebsvBegleitschein, sms_telephone_number: str):
        has_dangerous_waste = False
        for line in begleitschein.begleitschein_lines:
            if line.requires_reporting():
                has_dangerous_waste = True
                line.vebsv_id = self.transfer_service.request_vebsv_id()
        local_units = [LocalUnit("pickup_site", begleitschein.source_site.gtin, "9008390109199"),
                       LocalUnit("dropoff_site", begleitschein.target_site.gtin, "9008390109199")]

        self.message_service.create_begleitschein(local_units, begleitschein._get_shipment(), begleitschein,
                                                  sms_telephone_number)
        return has_dangerous_waste

    def start_transport(self, begleitschein: VebsvBegleitschein, message_name):
        transport_mean = TransportMean("Strasse", "9008390100059")

        self.message_service.start_transport(transport_mean, begleitschein, begleitschein._get_shipment(), message_name)

        for begleitschein_line in begleitschein.begleitschein_lines:
            if begleitschein_line.requires_reporting():
                self.transfer_service.declare_transport(
                    begleitschein.selected_organisations(),
                    begleitschein.selected_local_units(),
                    begleitschein_line.get_shipment_item(),
                    begleitschein_line.vebsv_id,
                    begleitschein.transport_uuid,
                    transport_mean,
                    begleitschein.selected_waypoints())
                if begleitschein.dropship_partner_id:
                    self.transfer_service.declare_dropship(
                        begleitschein.selected_organisations(),
                        begleitschein_line.vebsv_id)

    def end_transport(self, begleitschein: VebsvBegleitschein):
        self.message_service.end_transport(begleitschein, begleitschein._get_shipment())

        if begleitschein.is_target():
            for begleitschein_line in begleitschein.begleitschein_lines:
                if begleitschein_line.requires_reporting():
                    self.transfer_service.declare_takeover(
                        begleitschein.selected_organisations(),
                        begleitschein.selected_local_units(),
                        begleitschein_line.get_shipment_item(),
                        begleitschein_line.vebsv_id)
