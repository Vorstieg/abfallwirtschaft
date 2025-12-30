from odoo.addons.abfall_stammdaten.models.core_data.waste_revocation_reason import WasteRevocationReason

from .message.begleitschein_message_service import BegleitscheinMessageService
from .transfer.begleitschein_transfer_service import BegleitscheinTransferService
from .vebsv_begleitschein import VebsvBegleitschein, VebsvPartner


class VEBSVService:
    message_service: BegleitscheinMessageService
    transfer_service: BegleitscheinTransferService

    def __init__(self, auth):
        self.message_service = BegleitscheinMessageService(auth)
        self.transfer_service = BegleitscheinTransferService(auth)

    def start_begleitschein(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, sms_telephone_number: str):
        has_dangerous_waste = False
        for line in begleitschein.begleitschein_lines:
            if line.requires_reporting():
                has_dangerous_waste = True
                line.write_vebsv_id(self.transfer_service.request_vebsv_id())

        self.message_service.create_begleitschein(begleitschein, sender, sms_telephone_number)
        return has_dangerous_waste


    def confirm_begleitschein(self, begleitschein: VebsvBegleitschein):
        for begleitschein_line in begleitschein.begleitschein_lines:
            if begleitschein_line.requires_reporting():
                self.transfer_service.declare_handover(begleitschein, begleitschein_line)


    def start_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, message_name):
        if begleitschein.dropship_partner_id:
            for line in begleitschein.begleitschein_lines:
                if line.requires_reporting():
                    self.transfer_service.declare_dropship(begleitschein, line)

        self.message_service.declare_transport(begleitschein, sender, message_name)

        for line in begleitschein.begleitschein_lines:
            if line.requires_reporting():
                self.transfer_service.declare_transport(line, begleitschein)

        if sender.is_carrier(begleitschein):
            self.message_service.start_transport(begleitschein, sender)
            for line in begleitschein.begleitschein_lines:
                if line.requires_reporting():
                    self.transfer_service.start_transport(line, begleitschein)


    def end_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner):
        self.message_service.end_transport(begleitschein, sender)

        if sender.is_target(begleitschein):
            for line in begleitschein.begleitschein_lines:
                if line.requires_reporting():
                    self.transfer_service.declare_takeover(line, begleitschein)


    def cancel_declared(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, reason: WasteRevocationReason):
        self.message_service.cancel_create_begleitschein(begleitschein, sender, reason)


    def cancel_confirmed(self, begleitschein: VebsvBegleitschein, reason: WasteRevocationReason):
        for line in begleitschein.begleitschein_lines:
            if line.requires_reporting():
                self.transfer_service.cancel_declare_handover(line, reason)


    def cancel_in_transport(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, reason: WasteRevocationReason):
        if sender.is_carrier(begleitschein):
            for line in begleitschein.begleitschein_lines:
                    if line.requires_reporting():
                        self.transfer_service.cancel_start_transport(line, reason)
            self.message_service.cancel_start_transport(begleitschein, sender, reason)

        for line in begleitschein.begleitschein_lines:
            if line.requires_reporting():
                self.transfer_service.cancel_declare_transport(line, reason)

        self.message_service.cancel_declare_transport(begleitschein, sender, reason)

        for line in begleitschein.begleitschein_lines:
            if line.requires_reporting():
                if begleitschein.dropship_partner_id:
                    self.transfer_service.cancel_declare_dropship(line, reason)


    def cancel_done(self, begleitschein: VebsvBegleitschein, sender: VebsvPartner, reason: WasteRevocationReason):
        for line in begleitschein.begleitschein_lines:
            if line.requires_reporting():
                self.transfer_service.cancel_declare_takeover(line, reason)

        self.message_service.cancel_end_transport(begleitschein, sender, reason)

