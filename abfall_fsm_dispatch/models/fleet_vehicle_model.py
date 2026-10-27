from odoo import fields, models


class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    allowed_waste_type_ids = fields.Many2many(
        'waste.type',
        'fleet_vehicle_model_waste_type_rel',
        'vehicle_model_id',
        'waste_type_id',
        string='Allowed Waste Types',
        domain="[('dangerous', '!=', False)]",
        help='Dangerous waste types this vehicle model is allowed to transport.',
    )
    abfall_waste_management_enabled = fields.Boolean(
        string='Waste Management Enabled',
        compute='_compute_abfall_waste_management_enabled',
    )

    def _compute_abfall_waste_management_enabled(self):
        enabled = self.env['abfall.dispatch.list']._is_vehicle_waste_management_enabled()
        for model in self:
            model.abfall_waste_management_enabled = enabled
