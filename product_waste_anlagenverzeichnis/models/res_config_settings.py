from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    eras_api_user = fields.Char(string="eRAS API User", config_parameter='abfallwirtschaft.eras_api_user', help="Username for eRAS Registerabfrage")
    eras_api_password = fields.Char(string="eRAS API Password", config_parameter='abfallwirtschaft.eras_api_password', help="Password for eRAS Registerabfrage")
    eras_base_url = fields.Selection([
        ('https://secure.umweltbundesamt.at/eras/erasapi?wsdl', 'Production'),
        ('https://edmdemo.umweltbundesamt.at/eras/erasapi?wsdl', 'Test / Demo'),
    ], string="eRAS Environment", config_parameter='abfallwirtschaft.eras_base_url', default='https://secure.umweltbundesamt.at/eras/erasapi?wsdl', help="Select the eRAS environment (Production or Test)")
