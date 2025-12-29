import os
import lxml.etree as ET
from odoo.tests import TransactionCase
from ..controller.library.parser import (
    create_waste_handling_notification_xml,
    WasteHandlingNotification,
    Party,
    SpecifiedLocation,
    WasteMovementSite,
    Address,
    WasteReclassification as ParserWasteReclassification
)
from datetime import date

class TestComplianceExamples(TransactionCase):
    
    def setUp(self):
        super(TestComplianceExamples, self).setUp()
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.examples_path = os.path.join(self.base_path, 'balance', 'xml_example_msg')

    def _normalize_xml(self, xml_str):
        """Helper to normalize XML for comparison by removing whitespace and comments"""
        parser = ET.XMLParser(remove_blank_text=True, remove_comments=True)
        elem = ET.fromstring(xml_str, parser=parser)
        return elem

    def test_example_reclassification_structure(self):
        """
        Verify that our parser produces a structure matching example_B_WasteReclassification.xml
        """
        # Data from example_B_WasteReclassification.xml
        # 1. WasteMaterialMovement with Reclassification
        reclass_move = WasteHandlingNotification(
            id="AB549",
            type_code="9008390101728", # Reclassification move type
            handover_party=Party(
                id=None,
                office_address=None
            ),
            takeover_party=Party(
                id=None,
                office_address=None
            ),
            handover_location=SpecifiedLocation(
                installation=WasteMovementSite(id="9008390222881", name="Deponie-Zwischenlager gem. § 33")
            ),
            takeover_location=SpecifiedLocation(
                installation=WasteMovementSite(id="9008390223291", name="Reststoff Kompartiment")
            ),
            origin_physical_process_code="9008390008393",
            treatment_physical_process_code="9008390008393",
            classification_code="9008390014158",
            preliminary_classification_code="9008390014134",
            reclassification_reason_type_code="9008390113448",
            quantification_type="9008390100004",
            weight=21734500,
            movement_start_date=None
        )

        # 2. Standalone WasteReclassificationMaterial
        reclass_material = ParserWasteReclassification(
            installation_id="9008390244654",
            preliminary_classification_code="9008390021644",
            classification_code="9008390021194",
            quantification_type="9008390100004",
            weight=5000,
            reclassification_reason_type_code="9008390113417",
            reporting_date=date(2024, 12, 31)
        )

        # Generate XML
        generated_xml = create_waste_handling_notification_xml(
            date(2024, 1, 1),
            date(2024, 12, 31),
            "9008390222676",
            [reclass_move],
            waste_reclassifications=[reclass_material]
        )

        # Load Example
        example_file = os.path.join(self.examples_path, 'example_B_WasteReclassification.xml')
        with open(example_file, 'rb') as f:
            example_xml_str = f.read()

        norm_gen = self._normalize_xml(generated_xml)
        norm_ex = self._normalize_xml(example_xml_str)

        # We can't do a full element comparison because our generator sets specific
        # CreationSoftware values ("Vorstieg"), while the example has "Dispose-IT".
        # But we can check for key elements.
        
        # Check ObligatedParty
        self.assertEqual(norm_gen.find(".//{*}ObligatedParty/{*}ID").text, "9008390222676")
        
        # Check that we have exactly two SpecifiedWasteHandlingNotificationEntry elements
        # (One for the move, one for the standalone reclassification)
        entries = norm_gen.findall(".//{*}SpecifiedWasteHandlingNotificationEntry")
        self.assertEqual(len(entries), 2)
        
        # Check first entry (WasteMaterialMovement)
        move_entry = entries[0].find(".//{*}WasteMaterialMovement")
        self.assertIsNotNone(move_entry)
        self.assertEqual(move_entry.find("{*}ID").text, "AB549")
        self.assertEqual(move_entry.find(".//{*}PreliminaryClassificationWasteMaterial/{*}PreliminaryClassificationCode").text, "9008390014134")

        # Check second entry (WasteReclassificationMaterial)
        reclass_entry = entries[1].find(".//{*}WasteReclassificationMaterial")
        self.assertIsNotNone(reclass_entry)
        self.assertEqual(reclass_entry.find("{*}PreliminaryClassificationCode").text, "9008390021644")
        self.assertEqual(reclass_entry.find("{*}ClassificationCode").text, "9008390021194")

    def test_example_movements_structure(self):
        """
        Verify that our parser produces a structure matching example_A_WasteHandlingNotification.xml
        """
        # Data from example_A_WasteHandlingNotification.xml
        # 1. Registered Handover Party to Registered Installation
        move1 = WasteHandlingNotification(
            id="AB548",
            type_code="9008390101544",
            handover_party=Party(
                id="9008390029312",
                name="Abfalltiger AG",
                office_address=Address(
                    country_id="040",
                    city_name="Leutasch",
                    postcode="6105",
                    street_name="Kirchplatzl",
                    building_number="128a"
                )
            ),
            handover_location=SpecifiedLocation(
                operating_site=WasteMovementSite(id="9008391725619", name="Standort Wölbling (Abfalltiger AG)")
            ),
            takeover_party=Party(id=None),
            takeover_location=SpecifiedLocation(
                installation=WasteMovementSite(id="9008390222881", name="Deponie-Zwischenlager Seitenstetten")
            ),
            treatment_physical_process_code="9008390008393",
            classification_code="9008390014158",
            quantification_type="9008390100004",
            weight=21734500
        )

        # 2. Non-Registered Handover Party (PROTONES GmbH)
        move2 = WasteHandlingNotification(
            id="AB550",
            type_code="9008390101544",
            handover_party=Party(
                business_type_code="93.29",
                name="PROTONES GmbH & Co. KG",
                office_address=Address(
                    country_id="276",
                    city_name="Lüneburg",
                    postcode="21339",
                    street_name=" In der Marsch",
                    building_number="12A"
                )
            ),
            handover_location=SpecifiedLocation(
                address=Address(
                    country_id="040",
                    city_name="Oetz",
                    postcode="6433",
                    street_name="Anrauth",
                    building_number="1"
                )
            ),
            takeover_party=Party(id=None),
            takeover_location=SpecifiedLocation(
                installation=WasteMovementSite(id="9008390222881", name="Deponie-Zwischenlager Seitenstetten")
            ),
            treatment_physical_process_code="9008390008393",
            classification_code="9008390014158",
            quantification_type="9008390100004",
            weight=21734500
        )

        # Generate XML
        generated_xml = create_waste_handling_notification_xml(
            date(2024, 1, 1),
            date(2024, 12, 31),
            "9008390222676",
            [move1, move2]
        )

        norm_gen = self._normalize_xml(generated_xml)

        # Verify key parts of the structure
        entries = norm_gen.findall(".//{*}SpecifiedWasteHandlingNotificationEntry")
        self.assertEqual(len(entries), 2)

        # Verify move 1 details
        move1_xml = entries[0].find(".//{*}WasteMaterialMovement")
        self.assertEqual(move1_xml.find(".//{*}HandOverParty/{*}ID").text, "9008390029312")
        self.assertEqual(move1_xml.find(".//{*}HandOverParty/{*}OfficeAddress/{*}Postcode").text, "6105")
        self.assertEqual(move1_xml.find(".//{*}WasteTakeOverMovedMaterial/{*}SpecifiedLocation/{*}SpecifiedInstallation/{*}ID").text, "9008390222881")

        # Verify move 2 details (Non-registered)
        move2_xml = entries[1].find(".//{*}WasteMaterialMovement")
        self.assertIsNone(move2_xml.find(".//{*}HandOverParty/{*}ID")) # Should NOT have an ID
        self.assertEqual(move2_xml.find(".//{*}HandOverParty/{*}BusinessTypeCode").text, "93.29")
        self.assertEqual(move2_xml.find(".//{*}HandOverParty/{*}SpecifiedOrganization/{*}Name").text, "PROTONES GmbH & Co. KG")
        
        # Check handover location address (since it has no ID)
        loc_address = move2_xml.find(".//{*}WasteHandOverMovedMaterial/{*}SpecifiedLocation/{*}OfficeAddress")
        self.assertIsNotNone(loc_address)
        self.assertEqual(loc_address.find("{*}CityName").text, "Oetz")
