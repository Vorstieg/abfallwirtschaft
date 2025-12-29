# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from odoo.exceptions import UserError
from datetime import date


class TestAbfallBilanzExport(TransactionCase):

    def setUp(self):
        super(TestAbfallBilanzExport, self).setUp()
        
        # Setup test data
        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'person_gln': '9008390000007'
        })
        self.recipient = self.env['res.partner'].create({
            'name': 'Recipient Partner',
            'person_gln': '9008390000014'
        })
        
        self.abfallart = self.env['waste.type'].create({
            'name': 'Test Waste',
            'gtin': '9008390000021'
        })

        self.origin_type = self.env['waste.origin.type'].create({
            'name': 'Origin',
            'gtin': '9008390000069'
        })
        self.recycling_type = self.env['waste.recycling.type'].create({
            'name': 'Recycling', 
            'rdp_code': 'R1',
            'gtin': '9008390000052'
        })
        self.transport_type = self.env['waste.transport.type'].create({
            'name': 'Transport',
            'gtin': '9008390000076'
        })
        self.quant_type = self.env['waste.quantification.type'].create({
            'name': 'Quant',
            'gtin': '9008390000083'
        })
        
        # Create treatment site and installation
        self.treatment_site = self.env['waste.treatment.site'].create({
            'name': 'Test Site',
            'gtin': '9008390000038',
        })
        self.treatment_installation = self.env['waste.treatment.installation'].create({
            'name': 'Test Installation',
            'gtin': '9008390000045',
            'treatment_site_id': self.treatment_site.id,
        })

        # Create a move
        self.move = self.env['waste.move'].create({
            'name': 'Test Move',
            'origin_partner': self.partner.id,
            'recipient_partner': self.recipient.id,
            'abfallart': self.abfallart.id,
            'amount': 100.0,
            'state': 'approved',
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'origin_site': self.treatment_site.id,
            'origin_installation': self.treatment_installation.id,
            'recipient_site': self.treatment_site.id,
            'recipient_installation': self.treatment_installation.id,
            'date': date(2023, 6, 1),
        })
        
        # Create a submission record for testing
        self.submission = self.env['waste.bilanz.submission'].create({
            'name': 'Test Submission 2023',
            'year': '2023',
        })

    def test_validate_move_success(self):
        """Test validation passes with all required fields"""
        # Should not raise any exception
        self.submission._validate_move(self.move)

    def test_validate_move_missing_origin(self):
        """Test validation fails when origin partner is missing"""
        self.move.origin_partner = False
        with self.assertRaisesRegex(UserError, "Origin Partner is missing"):
            self.submission._validate_move(self.move)
            
    def test_validate_move_missing_recipient(self):
        """Test validation fails when recipient partner is missing"""
        self.move.recipient_partner = False
        with self.assertRaisesRegex(UserError, "Recipient Partner is missing"):
            self.submission._validate_move(self.move)
            
    def test_validate_move_missing_abfallart(self):
        """Test validation fails when waste type is missing"""
        self.move.abfallart = False
        with self.assertRaisesRegex(UserError, "Waste Type.*is missing"):
            self.submission._validate_move(self.move)

    def test_map_move(self):
        """Test mapping logic produces correct WasteHandlingNotification structure"""
        notification = self.submission.map_move(self.move)
        
        # Check simple fields
        self.assertEqual(notification.weight, 100.0)
        self.assertEqual(notification.classification_code, '9008390000021')  # Abfallart GTIN
        
        # Check dynamic types mapping
        self.assertEqual(notification.type_code, '9008390000076')  # transport_type.gtin
        self.assertEqual(notification.quantification_type, '9008390000083')  # quant_type.gtin

    def test_map_move_with_sites(self):
        """Test that sites and installations are correctly mapped"""
        notification = self.submission.map_move(self.move)
        
        # Check handover location (origin)
        self.assertIsNotNone(notification.handover_party)
        self.assertEqual(notification.handover_party.location.site.id, '9008390000038')
        self.assertEqual(notification.handover_party.location.installation.id, '9008390000045')
        
        # Check takeover location (recipient)
        self.assertIsNotNone(notification.takeover_party)
        self.assertEqual(notification.takeover_party.location.site.id, '9008390000038')
        self.assertEqual(notification.takeover_party.location.installation.id, '9008390000045')

    def test_map_address(self):
        """Test address mapping from partner"""
        self.partner.write({
            'street': 'Test Street 1',
            'zip': '1010',
            'city': 'Vienna',
            'country_id': self.env.ref('base.at').id,
        })
        
        address = self.submission._map_address(self.partner)
        
        self.assertEqual(address.street_name, 'Test Street 1')
        self.assertEqual(address.postcode, '1010')
        self.assertEqual(address.city_name, 'Vienna')
        self.assertEqual(address.country_id, '040')

    def test_map_party(self):
        """Test party mapping from partner"""
        party = self.submission._map_party(self.partner)
        
        self.assertEqual(party.id, '9008390000007')
        self.assertEqual(party.name, 'Test Partner')

    def test_generate_xml_data(self):
        """Test XML generation produces valid output"""
        # Ensure the company has required GLN
        self.env.company.partner_id.person_gln = '9008390000007'
        
        # Check that generate_xml_data runs without error
        xml_data = self.submission.generate_xml_data()
        
        self.assertIsNotNone(xml_data)
        self.assertIsInstance(xml_data, str)
        # Check that it's valid XML (starts with root element)
        self.assertTrue(xml_data.startswith('<'))


class TestCalculateInventory(TransactionCase):
    """Test cases for WasteBilanz.action_calculate_inventory method"""

    def setUp(self):
        super(TestCalculateInventory, self).setUp()
        
        # Create mandatory quantification type with required GTIN
        self.mandatory_quant_type = self.env['waste.quantification.type'].create({
            'name': 'Mandatory Quant Type',
            'gtin': '9008390100011'  # Required GTIN for inventory calculation
        })
        
        # Create waste type
        self.waste_type = self.env['waste.type'].create({
            'name': 'Test Waste Type',
            'gtin': '9008390000021'
        })
        
        # Link treatment site to company partner
        self.env.company.partner_id.person_gln = '9008390000007'
        
        self.treatment_site = self.env['waste.treatment.site'].create({
            'name': 'Company Site',
            'gtin': '9008390000038',
            'partner_id': self.env.company.partner_id.id,
        })
        
        self.installation = self.env['waste.treatment.installation'].create({
            'name': 'Company Installation',
            'gtin': '9008390000045',
            'treatment_site_id': self.treatment_site.id,
        })
        
        # Create the wizard
        self.wizard = self.env['waste.bilanz'].create({
            'year': '2023',
        })
        
        # Create helper data for moves
        self.external_partner = self.env['res.partner'].create({
            'name': 'External Partner',
            'person_gln': '9008390000014'
        })
        self.origin_type = self.env['waste.origin.type'].create({
            'name': 'Origin', 'gtin': '9008390000069'
        })
        self.recycling_type = self.env['waste.recycling.type'].create({
            'name': 'Recycling', 'rdp_code': 'R1', 'gtin': '9008390000052'
        })
        self.transport_type = self.env['waste.transport.type'].create({
            'name': 'Transport', 'gtin': '9008390000076'
        })
        self.quant_type = self.env['waste.quantification.type'].create({
            'name': 'Quant', 'gtin': '9008390000083'
        })

    def test_calculate_inventory_missing_quant_type(self):
        """Test that error is raised when mandatory quantification type is missing"""
        # Make sure ALL records with that GTIN are gone (in case of demo data)
        self.env['waste.quantification.type'].search([('gtin', '=', '9008390100011')]).unlink()
        
        with self.assertRaisesRegex(UserError, "Mandatory Waste Quantification Type"):
            self.wizard.action_calculate_inventory()

    def test_calculate_inventory_takeover_only(self):
        """Test inventory calculation with only takeover (incoming) moves"""
        # Create approved takeover move (recipient is our installation)
        self.env['waste.move'].create({
            'name': 'Takeover Move',
            'origin_partner': self.external_partner.id,
            'recipient_partner': self.env.company.partner_id.id,
            'abfallart': self.waste_type.id,
            'amount': 500.0,
            'state': 'approved',
            'recipient_installation': self.installation.id,
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'date': date(2023, 6, 15),
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        # Check storage state was created
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        self.assertEqual(len(state), 1)
        self.assertEqual(state.amount, 500.0)

    def test_calculate_inventory_handover_only(self):
        """Test inventory calculation with only handover (outgoing) moves"""
        # Create approved handover move (origin is our installation)
        self.env['waste.move'].create({
            'name': 'Handover Move',
            'origin_partner': self.env.company.partner_id.id,
            'recipient_partner': self.external_partner.id,
            'abfallart': self.waste_type.id,
            'amount': 300.0,
            'state': 'approved',
            'origin_installation': self.installation.id,
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'date': date(2023, 7, 20),
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        self.assertEqual(len(state), 1)
        self.assertEqual(state.amount, -300.0)  # Negative because only handover

    def test_calculate_inventory_with_previous_inventory(self):
        """Test that previous approved inventory is carried forward"""
        # Create approved storage state from previous year
        self.env['waste.storage.state'].create({
            'installation_id': self.installation.id,
            'abfallart': self.waste_type.id,
            'reporting_date': date(2022, 12, 31),
            'amount': 1000.0,
            'quantification_type': self.mandatory_quant_type.id,
            'state': 'approved',
            'company_id': self.env.company.id,
        })
        
        # Create a takeover in 2023
        self.env['waste.move'].create({
            'name': 'Takeover Move',
            'origin_partner': self.external_partner.id,
            'recipient_partner': self.env.company.partner_id.id,
            'abfallart': self.waste_type.id,
            'amount': 200.0,
            'state': 'approved',
            'recipient_installation': self.installation.id,
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'date': date(2023, 3, 10),
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        self.assertEqual(state.amount, 1200.0)  # 1000 + 200

    def test_calculate_inventory_with_corrections(self):
        """Test that storage corrections are included in calculation"""
        self.env['waste.storage.correction'].create({
            'installation_id': self.installation.id,
            'abfallart': self.waste_type.id,
            'reporting_date': date(2023, 5, 1),
            'amount': 150.0,  # Positive correction
            'quantification_type': self.mandatory_quant_type.id,
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        self.assertEqual(state.amount, 150.0)

    def test_calculate_inventory_with_reclassification_in(self):
        """Test that reclassification INTO this waste type adds to inventory"""
        other_waste_type = self.env['waste.type'].create({
            'name': 'Other Waste', 'gtin': 'OTHER_GTIN'
        })
        
        self.env['waste.reclassification'].create({
            'installation_id': self.installation.id,
            'preliminary_abfallart': other_waste_type.id,  # From this type
            'new_abfallart': self.waste_type.id,           # To our type (adds)
            'reporting_date': date(2023, 8, 15),
            'amount': 250.0,
            'quantification_type': self.mandatory_quant_type.id,
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        self.assertEqual(state.amount, 250.0)

    def test_calculate_inventory_with_reclassification_out(self):
        """Test that reclassification OUT of this waste type subtracts from inventory"""
        other_waste_type = self.env['waste.type'].create({
            'name': 'Other Waste', 'gtin': 'OTHER_GTIN'
        })
        
        self.env['waste.reclassification'].create({
            'installation_id': self.installation.id,
            'preliminary_abfallart': self.waste_type.id,    # From our type (subtracts)
            'new_abfallart': other_waste_type.id,           # To other type
            'reporting_date': date(2023, 9, 20),
            'amount': 100.0,
            'quantification_type': self.mandatory_quant_type.id,
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        self.assertEqual(state.amount, -100.0)

    def test_calculate_inventory_full_formula(self):
        """Test complete formula: Previous + Takeovers - Handovers + Corrections + ReclassIn - ReclassOut"""
        other_waste_type = self.env['waste.type'].create({
            'name': 'Other Waste', 'gtin': 'OTHER_GTIN'
        })
        
        # Previous inventory: 1000
        self.env['waste.storage.state'].create({
            'installation_id': self.installation.id,
            'abfallart': self.waste_type.id,
            'reporting_date': date(2022, 12, 31),
            'amount': 1000.0,
            'quantification_type': self.mandatory_quant_type.id,
            'state': 'approved',
            'company_id': self.env.company.id,
        })
        
        # Takeover: +500
        self.env['waste.move'].create({
            'name': 'Takeover',
            'origin_partner': self.external_partner.id,
            'recipient_partner': self.env.company.partner_id.id,
            'abfallart': self.waste_type.id,
            'amount': 500.0,
            'state': 'approved',
            'recipient_installation': self.installation.id,
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'date': date(2023, 2, 1),
            'company_id': self.env.company.id,
        })
        
        # Handover: -200
        self.env['waste.move'].create({
            'name': 'Handover',
            'origin_partner': self.env.company.partner_id.id,
            'recipient_partner': self.external_partner.id,
            'abfallart': self.waste_type.id,
            'amount': 200.0,
            'state': 'approved',
            'origin_installation': self.installation.id,
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'date': date(2023, 4, 1),
            'company_id': self.env.company.id,
        })
        
        # Correction: +50
        self.env['waste.storage.correction'].create({
            'installation_id': self.installation.id,
            'abfallart': self.waste_type.id,
            'reporting_date': date(2023, 5, 1),
            'amount': 50.0,
            'quantification_type': self.mandatory_quant_type.id,
            'company_id': self.env.company.id,
        })
        
        # Reclassification in: +100
        self.env['waste.reclassification'].create({
            'installation_id': self.installation.id,
            'preliminary_abfallart': other_waste_type.id,
            'new_abfallart': self.waste_type.id,
            'reporting_date': date(2023, 6, 1),
            'amount': 100.0,
            'quantification_type': self.mandatory_quant_type.id,
            'company_id': self.env.company.id,
        })
        
        # Reclassification out: -75
        self.env['waste.reclassification'].create({
            'installation_id': self.installation.id,
            'preliminary_abfallart': self.waste_type.id,
            'new_abfallart': other_waste_type.id,
            'reporting_date': date(2023, 7, 1),
            'amount': 75.0,
            'quantification_type': self.mandatory_quant_type.id,
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        
        # Expected: 1000 + 500 - 200 + 50 + 100 - 75 = 1375
        self.assertEqual(state.amount, 1375.0)

    def test_calculate_inventory_ignores_draft_moves(self):
        """Test that draft (unapproved) moves are not counted"""
        self.env['waste.move'].create({
            'name': 'Draft Move',
            'origin_partner': self.external_partner.id,
            'recipient_partner': self.env.company.partner_id.id,
            'abfallart': self.waste_type.id,
            'amount': 999.0,
            'state': 'draft',  # Not approved
            'recipient_installation': self.installation.id,
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'date': date(2023, 6, 15),
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        # No state should be created because draft moves are ignored
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        self.assertEqual(len(state), 0)

    def test_calculate_inventory_respects_year_boundary(self):
        """Test that only moves within the selected year are counted"""
        # Move in 2022 (should be ignored)
        self.env['waste.move'].create({
            'name': 'Old Move',
            'origin_partner': self.external_partner.id,
            'recipient_partner': self.env.company.partner_id.id,
            'abfallart': self.waste_type.id,
            'amount': 1000.0,
            'state': 'approved',
            'recipient_installation': self.installation.id,
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'date': date(2022, 12, 31),
            'company_id': self.env.company.id,
        })
        
        # Move in 2023 (should be counted)
        self.env['waste.move'].create({
            'name': 'Current Year Move',
            'origin_partner': self.external_partner.id,
            'recipient_partner': self.env.company.partner_id.id,
            'abfallart': self.waste_type.id,
            'amount': 100.0,
            'state': 'approved',
            'recipient_installation': self.installation.id,
            'origin_type': self.origin_type.id,
            'recycling_type': self.recycling_type.id,
            'transport_type': self.transport_type.id,
            'quantification_type': self.quant_type.id,
            'date': date(2023, 1, 1),
            'company_id': self.env.company.id,
        })
        
        self.wizard.action_calculate_inventory()
        
        state = self.env['waste.storage.state'].search([
            ('installation_id', '=', self.installation.id),
            ('abfallart', '=', self.waste_type.id),
            ('reporting_date', '=', date(2023, 12, 31)),
        ])
        self.assertEqual(state.amount, 100.0)  # Only 2023 move counted
