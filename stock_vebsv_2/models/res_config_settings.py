import uuid

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
    edm_db_uuid = fields.Char(
        string="EDM DB UUID",
        config_parameter='waste_management.edm_db_uuid',
        help="UUID used to identify application for polling message ws",
        default=uuid.uuid4()
    )
    edm_last_transaction_uuid = fields.Char(
        string="UUID of the last transaction fetched from the message service",
        config_parameter='waste_management.edm_last_transaction_uuid',
        help="UUID to track, which messages have already been processed",
        default="00000000-0000-0000-0000-000000000000"
    )
