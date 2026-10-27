from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    abfall_dispatch_vehicle_waste_management = fields.Boolean(
        string='Check vehicle waste type approvals',
        config_parameter='abfall_fsm_dispatch.vehicle_waste_management',
    )
