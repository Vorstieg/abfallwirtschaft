# -*- coding: utf-8 -*-

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'abfall_fsm_dispatch')
class TestVehicleWasteWarning(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'Waste Customer'})
        cls.warehouse = cls.env.user._get_default_warehouse_id()
        cls.customer_location = cls.env['stock.location'].create({
            'name': 'Waste Customer Location',
            'usage': 'customer',
            'company_id': cls.company.id,
        })
        cls.waste_type = cls.env['waste.type'].create({
            'name': 'Hazardous Test Waste',
            'key_number': '99999',
            'dangerous': 'g',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Hazardous Product',
            'is_storable': True,
            'waste_type_id': cls.waste_type.id,
        })
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Dispatch Brand'})
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Dispatch Truck',
            'brand_id': cls.brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'DISP-1',
        })

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            'abfall_fsm_dispatch.vehicle_waste_management',
            'True',
        )

    def _create_picking(self):
        return self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.customer_location.id,
            'company_id': self.company.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom': self.product.uom_id.id,
                'location_id': self.warehouse.lot_stock_id.id,
                'location_dest_id': self.customer_location.id,
                'company_id': self.company.id,
                'description_picking': self.product.display_name,
            })],
        })

    def test_warns_when_vehicle_model_lacks_hazardous_waste_type(self):
        dispatch = self.env['abfall.dispatch.list'].create({
            'company_id': self.company.id,
            'vehicle_id': self.vehicle.id,
            'picking_ids': [Command.link(self._create_picking().id)],
        })

        self.assertEqual(dispatch.hazardous_waste_type_ids, self.waste_type)
        self.assertEqual(dispatch.vehicle_missing_waste_type_ids, self.waste_type)
        self.assertIn('Hazardous Test Waste', dispatch.vehicle_waste_warning)
        self.assertIn('Warnung:', dispatch.vehicle_waste_warning)
        self.assertIn('nicht freigegeben', dispatch.vehicle_waste_warning)
        self.assertNotIn('<strong>', dispatch.vehicle_waste_warning)

    def test_no_warning_when_vehicle_model_allows_hazardous_waste_type(self):
        self.vehicle_model.allowed_waste_type_ids = [Command.link(self.waste_type.id)]
        dispatch = self.env['abfall.dispatch.list'].create({
            'company_id': self.company.id,
            'vehicle_id': self.vehicle.id,
            'picking_ids': [Command.link(self._create_picking().id)],
        })

        self.assertFalse(dispatch.vehicle_missing_waste_type_ids)
        self.assertFalse(dispatch.vehicle_waste_warning)
