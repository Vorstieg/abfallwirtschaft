# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ContainerExchangeWizard(models.TransientModel):
    _name = 'container.exchange.wizard'
    _description = 'Container Exchange Wizard'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related='sale_order_id.company_id',
        string='Company',
        readonly=True,
    )
    returnable_lot_ids = fields.Many2many(
        'stock.lot',
        string='Returnable Containers',
        compute='_compute_container_lot_domains',
    )
    deliverable_lot_ids = fields.Many2many(
        'stock.lot',
        string='Deliverable Containers',
        compute='_compute_container_lot_domains',
    )
    return_lot_id = fields.Many2one(
        'stock.lot',
        string='Container to Return',
        domain="[('id', 'in', returnable_lot_ids)]",
        help='Serial number of the container that is picked up from the customer.',
    )
    delivery_lot_id = fields.Many2one(
        'stock.lot',
        string='Container to Deliver',
        domain="[('id', 'in', deliverable_lot_ids)]",
        help='Serial number of the container that is delivered to the customer.',
    )

    @api.depends('sale_order_id')
    def _compute_container_lot_domains(self):
        for wizard in self:
            order = wizard.sale_order_id
            rental_lines = order.order_line.filtered(
                lambda line: line.is_rental and line.product_id.tracking == 'serial'
            )
            products = rental_lines.product_id
            warehouse_location = order.warehouse_id.lot_stock_id
            rental_location = order._get_container_exchange_rental_location()
            returnable_lots = order._get_container_exchange_available_lots(products, rental_location)
            returnable_lots |= rental_lines.move_ids.filtered(
                lambda move: (
                    move.state == 'done'
                    and move.product_id.tracking == 'serial'
                    and move.location_dest_id == rental_location
                )
            ).lot_ids
            returned_lots = rental_lines.returned_lot_ids | rental_lines.move_ids.filtered(
                lambda move: move.state == 'done' and move.location_id == rental_location
            ).lot_ids
            returnable_lots -= returned_lots
            deliverable_lots = order._get_container_exchange_available_lots(products, warehouse_location)
            deliverable_lots -= returnable_lots
            wizard.returnable_lot_ids = returnable_lots
            wizard.deliverable_lot_ids = deliverable_lots

    def action_confirm(self):
        self.ensure_one()
        if not self.return_lot_id or not self.delivery_lot_id:
            raise UserError(_('Select both container serial numbers.'))
        self.sale_order_id._create_container_exchange_pickings(
            return_lot=self.return_lot_id,
            delivery_lot=self.delivery_lot_id,
        )
        return self.sale_order_id.action_view_container_exchange_pickings()
