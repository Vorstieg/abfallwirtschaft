from odoo import api, fields, models
from odoo.exceptions import ValidationError

from stdnum import ean
from stdnum.exceptions import InvalidChecksum, InvalidFormat, InvalidLength

class Partner(models.Model):
    _inherit = 'res.partner'

    waste_treatment_sites = fields.One2many(
        comodel_name='waste.treatment.site',
        inverse_name='partner_id', string='Waste Treatment Sites',)
    person_gln = fields.Char(string='Person GLN')

    @api.constrains('person_gln')
    def _check_person_gln(self):
        for record in self:
            if record.person_gln:
                try:
                    ean.validate(self.person_gln)
                except (InvalidChecksum, InvalidFormat, InvalidLength):
                    raise ValidationError("The person GLN is not valid")