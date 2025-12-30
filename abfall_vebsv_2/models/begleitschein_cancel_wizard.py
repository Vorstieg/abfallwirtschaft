# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BegleitscheinCancelWizard(models.TransientModel):
    _name = 'begleitschein.cancel.wizard'
    _description = 'Begleitschein Cancel Wizard'

    begleitschein_id = fields.Many2one('waste.begleitschein', string='Begleitschein', required=True)
    revocation_reason_id = fields.Many2one('waste.revocation.reason', string="Revocation Reason", required=True)

    def action_cancel_begleitschein(self):
        self.ensure_one()
        self.begleitschein_id.action_cancel(self.revocation_reason_id)
        return {'type': 'ir.actions.act_window_close'}
