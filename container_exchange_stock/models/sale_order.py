# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    container_exchange_in_picking_id = fields.Many2one(
        'stock.picking',
        string='Container Return',
        readonly=True,
        copy=False,
    )
    container_exchange_out_picking_id = fields.Many2one(
        'stock.picking',
        string='Container Delivery',
        readonly=True,
        copy=False,
    )
    container_exchange_picking_ids = fields.Many2many(
        'stock.picking',
        'container_exchange_sale_order_stock_picking_rel',
        'sale_order_id',
        'picking_id',
        string='All Container Exchange Transfers',
        readonly=True,
        copy=False,
    )
    container_exchange_picking_count = fields.Integer(
        string='Container Exchange Transfers',
        compute='_compute_container_exchange_picking_count',
    )

    def _compute_container_exchange_picking_count(self):
        for order in self:
            pickings = order.container_exchange_picking_ids
            if not pickings:
                pickings = order.container_exchange_in_picking_id | order.container_exchange_out_picking_id
            order.container_exchange_picking_count = len(pickings.exists())

    def action_create_container_exchange_pickings(self):
        self.ensure_one()
        if not self._is_container_exchange_allowed_state():
            raise UserError(_('Container exchange is only available in Picked-Up status.'))
        if self.container_exchange_in_picking_id or self.container_exchange_out_picking_id or self.container_exchange_picking_ids:
            raise UserError(_('Container exchange transfers already exist for this sales order.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Container Exchange'),
            'res_model': 'container.exchange.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('container_exchange_stock.view_container_exchange_wizard_form').id,
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }

    def _is_container_exchange_allowed_state(self):
        self.ensure_one()
        return self.rental_status == 'return'

    def action_view_container_exchange_pickings(self):
        self.ensure_one()
        pickings = (
            self.container_exchange_picking_ids or
            self.container_exchange_in_picking_id |
            self.container_exchange_out_picking_id
        ).exists()
        action = self.env['ir.actions.actions']._for_xml_id('stock.action_picking_tree_all')
        action['domain'] = [('id', 'in', pickings.ids)]
        action['context'] = {'create': False}
        if len(pickings) == 1:
            action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = pickings.id
        return action

    def _create_container_exchange_pickings(
        self,
        return_lot,
        delivery_lot,
    ):
        self.ensure_one()
        if self.container_exchange_in_picking_id or self.container_exchange_out_picking_id or self.container_exchange_picking_ids:
            raise UserError(_('Container exchange transfers already exist for this sales order.'))

        if not return_lot or not delivery_lot:
            raise UserError(_('Select both the container serial number to return and the container serial number to deliver.'))
        if return_lot == delivery_lot:
            raise UserError(_('Select two different container serial numbers.'))

        warehouse = self.warehouse_id
        if not warehouse:
            raise UserError(_('Select a warehouse on the sales order before creating the container exchange.'))

        incoming_type = warehouse.in_type_id
        outgoing_type = warehouse.out_type_id
        if not incoming_type or not outgoing_type:
            raise UserError(_('The selected warehouse needs incoming and outgoing operation types.'))

        stock_location = warehouse.lot_stock_id
        rental_location = self._get_container_exchange_rental_location()
        return_source_location = self._get_container_exchange_lot_location(
            return_lot,
            fallback_location=rental_location,
            parent_location=rental_location,
        )
        delivery_source_location = self._get_container_exchange_lot_location(
            delivery_lot,
            fallback_location=stock_location,
            parent_location=stock_location,
        )
        origin = _('%s - Container Exchange') % (self.name,)
        picking_vals = self._prepare_container_exchange_picking_vals

        incoming_picking = self.env['stock.picking'].create(picking_vals(
            picking_type=incoming_type,
            lot=return_lot,
            source_location=return_source_location,
            destination_location=stock_location,
            origin=origin,
        ))
        incoming_picking.action_confirm()
        outgoing_pickings = self._create_container_exchange_delivery_pickings(
            delivery_lot=delivery_lot,
            source_location=delivery_source_location,
            destination_location=rental_location,
            origin=origin,
        )
        incoming_picking._set_container_exchange_lot_done(return_lot)
        serial_picking = self._get_container_exchange_serial_picking(outgoing_pickings, delivery_lot, delivery_source_location)
        serial_picking._set_container_exchange_lot_done(delivery_lot)
        serial_picking.action_assign()
        outgoing_picking = self._get_container_exchange_final_delivery_picking(outgoing_pickings, rental_location)
        self.write({
            'container_exchange_in_picking_id': incoming_picking.id,
            'container_exchange_out_picking_id': outgoing_picking.id,
            'container_exchange_picking_ids': [(6, 0, (incoming_picking | outgoing_pickings).ids)],
        })
        return incoming_picking | outgoing_pickings

    def _get_container_exchange_rental_location(self):
        self.ensure_one()
        if not self.company_id.rental_loc_id:
            self.company_id._create_rental_location()
        if self.company_id.rental_loc_id:
            return self.company_id.rental_loc_id
        raise UserError(_('No rental stock location could be determined.'))

    def _get_container_exchange_lot_location(self, lot, fallback_location, parent_location=False):
        self.ensure_one()
        domain = [
            ('product_id', '=', lot.product_id.id),
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
            ('company_id', 'in', [False, self.company_id.id]),
        ]
        if parent_location:
            domain.append(('location_id', 'child_of', parent_location.id))
        quant = self.env['stock.quant'].search(domain, limit=1)
        return quant.location_id if quant else fallback_location

    def _get_container_exchange_available_lots(self, products, location):
        self.ensure_one()
        if not products or not location:
            return self.env['stock.lot']
        quants = self.env['stock.quant'].search([
            ('product_id', 'in', products.ids),
            ('lot_id', '!=', False),
            ('location_id', 'child_of', location.id),
            ('quantity', '>', 0),
            ('company_id', 'in', [False, self.company_id.id]),
        ])
        available_quants = quants.filtered(
            lambda quant: quant.quantity - quant.reserved_quantity > 0
        )
        return available_quants.lot_id

    def _prepare_container_exchange_picking_vals(
        self,
        picking_type,
        lot,
        source_location,
        destination_location,
        origin,
    ):
        self.ensure_one()
        product = lot.product_id
        vals = {
            'partner_id': self.partner_shipping_id.id or self.partner_id.id,
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': destination_location.id,
            'origin': origin,
            'company_id': self.company_id.id,
            'move_ids': [(0, 0, self._prepare_container_exchange_move_vals(
                product=product,
                source_location=source_location,
                destination_location=destination_location,
                origin=origin,
            ))],
        }
        if 'sale_id' in self.env['stock.picking']._fields:
            vals['sale_id'] = self.id
        group = self._get_container_exchange_procurement_group()
        if group and 'group_id' in self.env['stock.picking']._fields:
            vals['group_id'] = group.id
        return vals

    def _prepare_container_exchange_move_vals(
        self,
        product,
        source_location,
        destination_location,
        origin,
    ):
        self.ensure_one()
        move_vals = {
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'product_uom': product.uom_id.id,
            'location_id': source_location.id,
            'location_dest_id': destination_location.id,
            'company_id': self.company_id.id,
            'origin': origin,
        }
        move_fields = self.env['stock.move']._fields
        if 'description_picking' in move_fields:
            move_vals['description_picking'] = product.display_name
        elif 'name' in move_fields:
            move_vals['name'] = product.display_name
        if 'procure_method' in move_fields:
            move_vals['procure_method'] = 'make_to_stock'
        return move_vals

    def _create_container_exchange_delivery_pickings(
        self,
        delivery_lot,
        source_location,
        destination_location,
        origin,
    ):
        self.ensure_one()
        Move = self.env['stock.move']
        moves_before = Move.search([('origin', '=', origin)])
        product = delivery_lot.product_id
        procurement = self.env['stock.rule'].Procurement(
            product,
            1.0,
            product.uom_id,
            destination_location,
            product.display_name,
            origin,
            self.company_id,
            self._prepare_container_exchange_delivery_procurement_values(
                product=product,
                source_location=source_location,
                destination_location=destination_location,
                origin=origin,
            ),
        )
        self.env['stock.rule'].run([procurement])
        moves = Move.search([
            ('origin', '=', origin),
            ('product_id', '=', product.id),
            ('company_id', '=', self.company_id.id),
            ('id', 'not in', moves_before.ids),
        ])
        moves = self._get_container_exchange_related_moves(moves)
        pickings = moves.picking_id.exists()
        if not pickings:
            raise UserError(_('No delivery transfer could be created for the container exchange route.'))
        return pickings

    def _get_container_exchange_related_moves(self, moves):
        related_moves = moves
        pending_moves = moves
        while pending_moves:
            next_moves = (pending_moves.move_orig_ids | pending_moves.move_dest_ids) - related_moves
            related_moves |= next_moves
            pending_moves = next_moves
        return related_moves

    def _prepare_container_exchange_delivery_procurement_values(
        self,
        product,
        source_location,
        destination_location,
        origin,
    ):
        self.ensure_one()
        values = {
            'origin': origin,
            'date_planned': fields.Datetime.now(),
            'date_deadline': fields.Datetime.now(),
            'warehouse_id': self.warehouse_id,
            'route_ids': self._get_container_exchange_delivery_routes(),
            'partner_id': self.partner_shipping_id.id or self.partner_id.id,
            'location_final_id': destination_location,
            'company_id': self.company_id,
        }
        if 'stock_reference_ids' in self._fields:
            if not self.stock_reference_ids:
                self.env['stock.reference'].create({
                    'name': self.name,
                    'sale_ids': [(4, self.id)],
                })
            values['reference_ids'] = self.stock_reference_ids
        sale_line = self.order_line.filtered(lambda line: line.product_id == product)[:1]
        if sale_line and 'sale_line_id' in self.env['stock.move']._fields:
            values.update({
                'sale_line_id': sale_line.id,
                'sequence': sale_line.sequence,
            })
        if 'procurement_values' in self.env['stock.move']._fields:
            values['procurement_values'] = {
                'container_exchange_source_location_id': source_location.id,
            }
        return values

    def _get_container_exchange_delivery_routes(self):
        self.ensure_one()
        sale_line_routes = self.order_line.route_ids
        if sale_line_routes:
            return sale_line_routes
        rental_route = self.env.ref('sale_stock_renting.route_rental', raise_if_not_found=False)
        if rental_route and rental_route.active:
            return rental_route
        return self.warehouse_id.delivery_route_id

    def _get_container_exchange_serial_picking(self, pickings, delivery_lot, source_location):
        self.ensure_one()
        moves = pickings.move_ids.filtered(lambda move: (
            move.product_id == delivery_lot.product_id
            and move.state != 'cancel'
            and move.location_id._child_of(source_location)
        )).sorted('id')
        if not moves:
            moves = pickings.move_ids.filtered(lambda move: (
                move.product_id == delivery_lot.product_id
                and move.state != 'cancel'
                and not move.move_orig_ids
            )).sorted('id')
        if not moves:
            raise UserError(_('No container delivery move could be found for the selected serial number.'))
        return moves[:1].picking_id

    def _get_container_exchange_final_delivery_picking(self, pickings, destination_location):
        self.ensure_one()
        final_pickings = pickings.filtered(lambda picking: picking.location_dest_id == destination_location)
        if final_pickings:
            return final_pickings.sorted('id')[-1:]
        final_moves = pickings.move_ids.filtered(lambda move: (
            (move.location_final_id or move.location_dest_id) == destination_location
            and not move.move_dest_ids
        )).sorted('id')
        final_move_pickings = final_moves.picking_id
        if final_move_pickings:
            return final_move_pickings.sorted('id')[-1:]
        return pickings.sorted('id')[-1:]

    def _get_container_exchange_procurement_group(self):
        self.ensure_one()
        for field_name in ('procurement_group_id', 'group_id'):
            if field_name in self._fields and self[field_name]:
                return self[field_name]
        return False


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _set_container_exchange_lot_done(self, lot):
        self.ensure_one()
        move = self.move_ids.filtered(lambda stock_move: stock_move.product_id == lot.product_id)[:1]
        if not move:
            return
        move.move_line_ids.unlink()
        self.env['stock.move.line'].create({
            'picking_id': self.id,
            'move_id': move.id,
            'product_id': lot.product_id.id,
            'product_uom_id': lot.product_id.uom_id.id,
            'quantity': 1.0,
            'lot_id': lot.id,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
            'company_id': self.company_id.id,
        })
