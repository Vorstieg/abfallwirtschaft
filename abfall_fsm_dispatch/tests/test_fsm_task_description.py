# -*- coding: utf-8 -*-

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'abfall_fsm_dispatch')
class TestFsmTaskDescription(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Dispatch Customer',
            'street': 'Pickup Street 1',
            'city': 'Vienna',
            'zip': '1010',
        })
        cls.warehouse = cls.env.user._get_default_warehouse_id()
        cls.customer_location = cls.env['stock.location'].create({
            'name': 'Dispatch Customer Location',
            'usage': 'customer',
            'company_id': cls.company.id,
        })
        cls.fsm_project = cls.env['project.project'].create({
            'name': 'Dispatch FSM Project',
            'is_fsm': True,
            'company_id': cls.company.id,
        })
        cls.dispatch = cls.env['abfall.dispatch.list'].create({
            'company_id': cls.company.id,
            'description': 'Call before arrival',
        })
        cls.dispatch._ensure_fsm_project_worksheet(cls.fsm_project)
        cls.worksheet_template = cls.env.ref('abfall_fsm_dispatch.abfall_dispatch_worksheet_template')

    def _create_picking(self, picking_type, source_location, destination_location, product, lot=False):
        picking = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': destination_location.id,
            'company_id': self.company.id,
            'move_ids': [Command.create({
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'product_uom': product.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': destination_location.id,
                'company_id': self.company.id,
                'description_picking': product.display_name,
            })],
        })
        if lot:
            self.env['stock.move.line'].create({
                'picking_id': picking.id,
                'move_id': picking.move_ids.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': destination_location.id,
                'lot_id': lot.id,
                'quantity': 1.0,
                'company_id': self.company.id,
            })
        return picking

    def test_serial_container_pickup_is_written_to_task_description(self):
        product = self.env['product.product'].create({
            'name': 'Rental Container 10m3',
            'is_storable': True,
            'tracking': 'serial',
        })
        lot = self.env['stock.lot'].create({
            'name': 'CONT-00123',
            'product_id': product.id,
            'company_id': self.company.id,
        })
        picking = self._create_picking(
            self.warehouse.in_type_id,
            self.customer_location,
            self.warehouse.lot_stock_id,
            product,
            lot=lot,
        )

        vals = self.dispatch._prepare_fsm_task_vals(picking, self.fsm_project)

        self.assertIn('Arbeitsanweisungen', vals['description'])
        self.assertIn('Abholung:', vals['description'])
        self.assertIn('Produkt: Rental Container 10m3', vals['description'])
        self.assertIn('Container-Seriennummer: CONT-00123', vals['description'])
        self.assertIn('Menge:', vals['description'])
        self.assertNotIn('Work Instructions', vals['description'])
        self.assertNotIn('Container Serial:', vals['description'])
        self.assertEqual(vals['worksheet_template_id'], self.worksheet_template.id)

    def test_product_only_delivery_is_written_to_task_description(self):
        product = self.env['product.product'].create({
            'name': 'Mixed Waste',
            'is_storable': True,
        })
        picking = self._create_picking(
            self.warehouse.out_type_id,
            self.warehouse.lot_stock_id,
            self.customer_location,
            product,
        )

        vals = self.dispatch._prepare_fsm_task_vals(picking, self.fsm_project)

        self.assertIn('Lieferung:', vals['description'])
        self.assertIn('Produkt: Mixed Waste', vals['description'])
        self.assertNotIn('Container-Seriennummer:', vals['description'])
        self.assertNotIn('Delivery:', vals['description'])
        self.assertIn(self.warehouse.lot_stock_id.display_name, vals['description'])
        self.assertIn(self.customer_location.display_name, vals['description'])

    def test_weigh_quantity_posts_message_on_picking(self):
        kg_uom = self.env.ref('uom.product_uom_kgm')
        product = self.env['product.product'].create({
            'name': 'Weighted Waste',
            'is_storable': True,
            'uom_id': kg_uom.id,
        })
        picking = self._create_picking(
            self.warehouse.in_type_id,
            self.customer_location,
            self.warehouse.lot_stock_id,
            product,
        )
        move = picking.move_ids
        move.product_uom_qty = 10.0

        message_count = len(picking.message_ids)
        move.action_weigh_quantity()

        self.assertEqual(len(picking.message_ids), message_count + 1)
        self.assertAlmostEqual(move.quantity, 9.0)
        self.assertIn('Menge verwogen', picking.message_ids[:1].body)
        self.assertIn('Weighted Waste', picking.message_ids[:1].body)
