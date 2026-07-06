# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'container_exchange_stock')
class TestContainerExchange(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Container Customer'})
        cls.warehouse = cls.env.user._get_default_warehouse_id()
        cls.company = cls.warehouse.company_id
        if not cls.company.rental_loc_id:
            cls.company._create_rental_location()
        cls.product = cls.env['product.product'].create({
            'name': 'Rental Container 10m3',
            'is_storable': True,
            'tracking': 'serial',
        })
        if 'rent_ok' in cls.product._fields:
            cls.product.rent_ok = True

        cls.return_lot = cls.env['stock.lot'].create({
            'name': 'CONT-RETURN',
            'product_id': cls.product.id,
            'company_id': cls.company.id,
        })
        cls.delivery_lot = cls.env['stock.lot'].create({
            'name': 'CONT-DELIVER',
            'product_id': cls.product.id,
            'company_id': cls.company.id,
        })
        cls.env['stock.quant']._update_available_quantity(
            cls.product,
            cls.company.rental_loc_id,
            1.0,
            lot_id=cls.return_lot,
        )
        cls.env['stock.quant']._update_available_quantity(
            cls.product,
            cls.warehouse.lot_stock_id,
            1.0,
            lot_id=cls.delivery_lot,
        )

        now = fields.Datetime.now()
        cls.order = cls.env['sale.order'].with_context(in_rental_app=True).create({
            'partner_id': cls.partner.id,
            'warehouse_id': cls.warehouse.id,
            'is_rental_order': True,
            'rental_start_date': now - timedelta(days=1),
            'rental_return_date': now + timedelta(days=1),
            'order_line': [Command.create({
                'product_id': cls.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 0.0,
                'is_rental': True,
                'qty_delivered': 1.0,
            })],
        })
        cls.order.action_confirm()

    def test_wizard_domains_and_exchange_pickings_use_serials(self):
        wizard = self.env['container.exchange.wizard'].create({
            'sale_order_id': self.order.id,
        })

        self.assertIn(self.return_lot, wizard.returnable_lot_ids)
        self.assertIn(self.delivery_lot, wizard.deliverable_lot_ids)

        pickings = self.order._create_container_exchange_pickings(
            return_lot=self.return_lot,
            delivery_lot=self.delivery_lot,
        )

        self.assertEqual(len(pickings), 2)
        self.assertEqual(self.order.container_exchange_in_picking_id.move_ids.product_id, self.product)
        self.assertEqual(self.order.container_exchange_out_picking_id.move_ids.product_id, self.product)
        self.assertEqual(self.order.container_exchange_in_picking_id.move_line_ids.lot_id, self.return_lot)
        self.assertEqual(self.order.container_exchange_out_picking_id.move_line_ids.lot_id, self.delivery_lot)

    def test_container_exchange_delivery_uses_native_rental_multi_step_route(self):
        self.env['res.config.settings'].create({'group_rental_stock_picking': True}).execute()
        self.warehouse.delivery_steps = 'pick_ship'

        pickings = self.order._create_container_exchange_pickings(
            return_lot=self.return_lot,
            delivery_lot=self.delivery_lot,
        )
        outgoing_pickings = pickings - self.order.container_exchange_in_picking_id

        self.assertEqual(len(outgoing_pickings), 1)
        self.assertEqual(outgoing_pickings.location_id, self.warehouse.lot_stock_id)
        self.assertEqual(outgoing_pickings.location_dest_id, self.warehouse.wh_output_stock_loc_id)
        self.assertNotEqual(outgoing_pickings.location_dest_id, self.company.rental_loc_id)
        self.assertEqual(outgoing_pickings.move_line_ids.lot_id, self.delivery_lot)
        self.assertEqual(self.order.container_exchange_out_picking_id, outgoing_pickings)

    def test_container_exchange_delivery_uses_multi_step_route(self):
        transit_location = self.env['stock.location'].create({
            'name': 'Container Exchange Transit',
            'usage': 'internal',
            'location_id': self.warehouse.view_location_id.id,
            'company_id': self.company.id,
        })
        route = self.env['stock.route'].create({
            'name': 'Container Exchange Two Step Route',
            'sale_selectable': True,
            'company_id': self.company.id,
            'rule_ids': [
                Command.create({
                    'name': 'Container Exchange Transit to Rental',
                    'action': 'pull',
                    'procure_method': 'make_to_order',
                    'location_src_id': transit_location.id,
                    'location_dest_id': self.company.rental_loc_id.id,
                    'location_dest_from_rule': True,
                    'picking_type_id': self.warehouse.out_type_id.id,
                    'warehouse_id': self.warehouse.id,
                    'company_id': self.company.id,
                }),
                Command.create({
                    'name': 'Container Exchange Stock to Transit',
                    'action': 'pull',
                    'procure_method': 'make_to_stock',
                    'location_src_id': self.warehouse.lot_stock_id.id,
                    'location_dest_id': transit_location.id,
                    'location_dest_from_rule': True,
                    'picking_type_id': self.warehouse.int_type_id.id,
                    'warehouse_id': self.warehouse.id,
                    'company_id': self.company.id,
                }),
            ],
        })
        self.order.order_line.route_ids = route

        pickings = self.order._create_container_exchange_pickings(
            return_lot=self.return_lot,
            delivery_lot=self.delivery_lot,
        )
        outgoing_pickings = pickings - self.order.container_exchange_in_picking_id
        first_outgoing = outgoing_pickings.filtered(
            lambda picking: picking.location_id == self.warehouse.lot_stock_id
        )
        final_outgoing = outgoing_pickings.filtered(
            lambda picking: picking.location_dest_id == self.company.rental_loc_id
        )

        self.assertEqual(len(pickings), 3)
        self.assertEqual(len(outgoing_pickings), 2)
        self.assertTrue(first_outgoing)
        self.assertTrue(final_outgoing)
        self.assertEqual(first_outgoing.location_dest_id, transit_location)
        self.assertEqual(final_outgoing.location_id, transit_location)
        self.assertEqual(first_outgoing.move_line_ids.lot_id, self.delivery_lot)
        self.assertEqual(self.order.container_exchange_out_picking_id, final_outgoing)
        self.assertEqual(self.order.container_exchange_picking_ids, pickings)
