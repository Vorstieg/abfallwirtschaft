from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    enable_sms_solution = fields.Boolean(string='Enable SMS solution', default=False)
    sms_solution_phone_number = fields.Char(string='Phone number for SMS solution')