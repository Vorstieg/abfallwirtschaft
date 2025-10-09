from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    enable_sms_solution = fields.Boolean(string='Enable SMS solution', default=False)
    sms_solution_phone_number = fields.Char(string='Phone number for SMS solution')

    def get_person_gln(self):
        try:
            return self.person_gln
        except AttributeError:
            raise UserError(f"User {self.name} has no GLN set")

    def is_carrier(self, begleitschein):
        return begleitschein.transport_partner_id == self

    def is_target(self, begleitschein):
        return begleitschein.target_partner_id == self
