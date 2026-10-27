from odoo import fields, models


class WeighbridgeStation(models.Model):
    _inherit = "weighbridge.station"

    warehouse_id = fields.Many2one("stock.warehouse", check_company=True)
    incoming_picking_type_id = fields.Many2one("stock.picking.type", check_company=True)
    outgoing_picking_type_id = fields.Many2one("stock.picking.type", check_company=True)
    source_location_id = fields.Many2one("stock.location", check_company=True)
    destination_location_id = fields.Many2one("stock.location", check_company=True)
    overdelivery_tolerance = fields.Float(
        default=0.0,
        help="Allowed over-delivery as a percentage of the selected order line quantity.",
    )
