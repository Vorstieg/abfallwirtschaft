from datetime import datetime
from typing import List

from .mappings import Shipment, ShipmentItem, Organisation, LocalUnit, PlannedWaypoint, Period, Recipient


class VebsvPartner():
    name: str

    def get_person_gln(self) -> str:
        return ""


class VebsvSite():
    gtin: str


class VebsvBegleitscheinLine():
    vebsv_id: str

    def requires_reporting(self) -> bool:
        pass

    def get_shipment_item(self) -> ShipmentItem:
        pass


class VebsvBegleitschein():
    self_is_main_organizer: bool
    shipment_uuid: str
    business_case_uuid: str
    transport_uuid: str
    source_partner_id: VebsvPartner
    target_partner_id: VebsvPartner
    dropship_partner_id: VebsvPartner
    company_partner_id: VebsvPartner
    transport_partner_id: VebsvPartner
    source_site: VebsvSite
    target_site: VebsvSite
    begleitschein_lines: List[VebsvBegleitscheinLine]

    def _get_shipment(self) -> Shipment:
        pass

    def restricted_recipient_glns(self, sms_telephone_number: str = False, source_leg=True) -> List[Recipient]:
        recipient_list: List[Recipient] = []
        if self.source_partner_id != self.company_partner_id and (
                not self.is_dropshipping_with_two_legs() or source_leg):
            recipient_list.append(Recipient(self.source_partner_id.get_person_gln(), sms_telephone_number))

        if self.target_partner_id != self.company_partner_id and (
                not self.is_dropshipping_with_two_legs() or not source_leg):
            recipient_list.append(Recipient(self.target_partner_id.get_person_gln()))

        if self.dropship_partner_id and self.dropship_partner_id != self.company_partner_id:
            recipient_list.append(Recipient(self.dropship_partner_id.get_person_gln()))

        return recipient_list

    def all_recipient_glns(self) -> List[Recipient]:
        return [
            Recipient(gln) for gln in [
                self.source_partner_id.get_person_gln(),
                self.target_partner_id.get_person_gln(),
                self.dropship_partner_id.get_person_gln()
            ] if gln and gln != self.company_partner_id.get_person_gln()
        ]

    def sender_gln(self):
        return self.company_partner_id.get_person_gln()

    # we don't send all organisations in all messages, since some participants might not be allowed to know of other pax
    # For dropshipping, two ug_un messages are sent to two set of pax. If source_leg is True, it means the message gets sent to all participants,
    # that take over the trash before company_partner takes over the trash. If it is false, it is afterward.
    def selected_organisations(self, source_leg=True) -> List[Organisation]:
        if not self.dropship_partner_id:
            return [Organisation(self.source_partner_id.get_person_gln(), "handover"),
                    Organisation(self.target_partner_id.get_person_gln(), "takeover")]
        elif not self.is_dropshipping_with_two_legs():
            return [Organisation(self.source_partner_id.get_person_gln(), "handover"),
                    Organisation(self.dropship_partner_id.get_person_gln(), "intermediate"),
                    Organisation(self.target_partner_id.get_person_gln(), "takeover")]
        elif source_leg:
            return [Organisation(self.source_partner_id.get_person_gln(), "handover"),
                    Organisation(self.dropship_partner_id.get_person_gln(), "takeover")]
        else:
            return [Organisation(self.dropship_partner_id.get_person_gln(), "handover"),
                    Organisation(self.target_partner_id.get_person_gln(), "takeover")]

    def selected_local_units(self, source_leg=True) -> List[LocalUnit]:
        if not self.is_dropshipping_with_two_legs():
            return [LocalUnit("pickup_site", self.source_site.gtin, "9008390109199"),
                    LocalUnit("dropoff_site", self.target_site.gtin, "9008390109199")]
        elif source_leg:
            return [LocalUnit("pickup_site", self.source_site.gtin, "9008390109199")]
        else:
            return [LocalUnit("dropoff_site", self.target_site.gtin, "9008390109199")]

    def selected_waypoints(self, source_leg=True) -> List[PlannedWaypoint]:
        pickup = PlannedWaypoint(Period(datetime.now(), datetime.now()), "pickup_site", "handover", True, False)
        dropoff = PlannedWaypoint(Period(datetime.now(), datetime.now()), "dropoff_site", "takeover", False, False)
        if not self.is_dropshipping_with_two_legs():
            return [pickup, dropoff]
        elif source_leg:
            return [pickup]
        else:
            return [dropoff]

    def is_dropshipping_with_two_legs(self):
        return self.dropship_partner_id and not (
                self.company_partner_id.get_person_gln() == self.target_partner_id.get_person_gln() or
                self.company_partner_id.get_person_gln() == self.source_partner_id.get_person_gln())
    def is_transporteur(self):
        return self.transport_partner_id == self.company_partner_id

    def is_target(self):
        return self.company_partner_id == self.target_partner_id
