# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date
from ..models.edm_validator import EDMValidator, EDMSeverity

class TestEDMValidator(TransactionCase):

    def setUp(self):
        super(TestEDMValidator, self).setUp()
        
        # Setup company
        self.env.company.partner_id.person_gln = '9008390000007'
        
        # Setup partners
        self.partner_registered = self.env['res.partner'].create({
            'name': 'Registered Partner',
            'person_gln': '9008390000014'
        })
        self.partner_unregistered = self.env['res.partner'].create({
            'name': 'Unregistered Partner',
            'city': 'Vienna',
            'zip': '1010'
        })
        
        # Setup waste type
        self.abfallart = self.env['waste.type'].create({
            'name': 'Test Waste',
            'gtin': '9008390000021'
        })

        # Setup site and installation
        self.site = self.env['waste.treatment.site'].create({
            'name': 'Test Site',
            'gtin': '9008390000038'
        })
        self.installation = self.env['waste.treatment.installation'].create({
            'name': 'Test Installation',
            'gtin': '9008390000045',
            'treatment_site_id': self.site.id
        })

        # Base types
        self.recycling_type = self.env['waste.recycling.type'].create({
            'name': 'R1', 'gtin': '9008390000052', 'rdp_code': 'R1'
        })
        self.origin_type = self.env['waste.origin.type'].create({
            'name': 'P1', 'gtin': '9008390000069'
        })
        self.quant_type = self.env['waste.quantification.type'].create({
            'name': 'Weight', 'gtin': '9008390100011'
        })

        # Validator
        self.validator = EDMValidator(self.env)
        
        # Submission
        self.submission = self.env['waste.bilanz.submission'].create({
            'name': 'Test 2023',
            'year': '2023',
            'company_id': self.env.company.id
        })

    def test_validate_obligated_party(self):
        # Successful GLN
        self.validator._validate_obligated_party(self.submission)
        self.assertFalse(self.validator.result.has_critical)
        
        # Missing GLN
        self.env.company.partner_id.person_gln = False
        self.validator.result.errors = []
        self.validator._validate_obligated_party(self.submission)
        self.assertTrue(self.validator.result.has_critical)
        self.assertEqual(self.validator.result.errors[0].rule_id, 'C316')
        
        # Invalid format - should raise ValidationError due to @api.constrains
        with self.assertRaises(ValidationError):
            self.env.company.partner_id.person_gln = 'abc'

    def test_validate_waste_move_mass(self):
        move = self.env['waste.move'].create({
            'name': 'Mass Test',
            'amount': -10,
            'abfallart': self.abfallart.id
        })
        
        # Negative mass (R131)
        self.validator._validate_waste_move(move)
        error_ids = [e.rule_id for e in self.validator.result.errors]
        self.assertIn('R131', error_ids)
        
        # Zero mass (R867)
        move.amount = 0
        self.validator.result.errors = []
        self.validator._validate_waste_move(move)
        error_ids = [e.rule_id for e in self.validator.result.errors]
        self.assertIn('R867', error_ids)

    def test_validate_waste_move_booking_types(self):
        # 1. Takeover (Recipient is own installation)
        move_takeover = self.env['waste.move'].create({
            'name': 'Takeover',
            'recipient_installation': self.installation.id,
            'abfallart': self.abfallart.id,
            'amount': 100
        })
        
        # Should have R979 (Origin missing) and R901 (Treatment procedure missing)
        self.validator.result.errors = []
        self.validator._validate_waste_move(move_takeover)
        error_ids = [e.rule_id for e in self.validator.result.errors]
        self.assertIn('R979', error_ids)
        self.assertIn('R901', error_ids)
        
        # Fix takeover
        move_takeover.write({
            'origin_partner': self.partner_registered.id,
            'recycling_type': self.recycling_type.id
        })
        self.validator.result.errors = []
        self.validator._validate_waste_move(move_takeover)
        self.assertNotIn('R979', [e.rule_id for e in self.validator.result.errors])
        self.assertNotIn('R901', [e.rule_id for e in self.validator.result.errors])

        # 2. Handover (Origin is own installation)
        move_handover = self.env['waste.move'].create({
            'name': 'Handover',
            'origin_installation': self.installation.id,
            'abfallart': self.abfallart.id,
            'amount': 100
        })
        
        # Should have R402 (Destination missing) and R108 (Origin procedure missing)
        self.validator.result.errors = []
        self.validator._validate_waste_move(move_handover)
        error_ids = [e.rule_id for e in self.validator.result.errors]
        self.assertIn('R402', error_ids)
        self.assertIn('R108', error_ids)

    def test_storage_consistency(self):
        # Create approved state
        state = self.env['waste.storage.state'].create({
            'installation_id': self.installation.id,
            'abfallart': self.abfallart.id,
            'reporting_date': date(2023, 12, 31),
            'amount': 1000,
            'quantification_type': self.quant_type.id,
            'state': 'approved'
        })
        
        # No moves -> Expected is 0. Diff is 1000.
        self.validator.result.errors = []
        self.validator._check_storage_consistency(state)
        error_ids = [e.rule_id for e in self.validator.result.errors]
        self.assertIn('CONSISTENCY', error_ids)
        
        # Create a takeover move to match the 1000
        self.env['waste.move'].create({
            'name': 'Matching Move',
            'origin_partner': self.partner_registered.id,
            'recipient_partner': self.env.company.partner_id.id,
            'recipient_installation': self.installation.id,
            'abfallart': self.abfallart.id,
            'amount': 1000,
            'quantification_type': self.quant_type.id,
            'date': date(2023, 1, 1),
            'state': 'approved'
        })
        
        self.validator.result.errors = []
        self.validator._check_storage_consistency(state)
        error_ids = [e.rule_id for e in self.validator.result.errors]
        self.assertNotIn('CONSISTENCY', error_ids)
