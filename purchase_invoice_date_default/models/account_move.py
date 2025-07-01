from odoo import models, fields, api
from datetime import date

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def create(self, vals):
        if 'invoice_date' not in vals:
            vals['invoice_date'] = date.today()
        return super(AccountMove, self).create(vals)