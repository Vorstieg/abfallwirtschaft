from odoo import fields, models, api

class WasteManagementConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    edm_username = fields.Char(
        string="EDM Username",
        config_parameter='waste_management.edm_username',
        help="Username for authenticating with EDM-"
    )
    edm_secret = fields.Char(
        string="EDM Application Key",
        config_parameter='waste_management.edm_secret',
        help="Secret key/password for authenticating with the EDM"
    )