from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.stock_vebsv_2.models.library.vebsv_begleitschein import VebsvPartner


class ResPartner(models.Model):
    _inherit = 'res.partner'

    enable_sms_solution = fields.Boolean(string='Enable SMS solution', default=False)
    sms_solution_phone_number = fields.Char(string='Phone number for SMS solution')

    def get_person_gln(self):
        # This assumes that the first id_number is the GLN
        # TODO: A more robust implementation might require a specific type of id_number
        try:
            return self.id_numbers.display_name
        except AttributeError:
            raise UserError(f"User {self.name} has no GLN set")

    def is_carrier(self, begleitschein):
        return begleitschein.transport_partner_id == self

    def is_target(self, begleitschein):
        return begleitschein.target_partner_id == self
