from odoo import models, fields, _

class WasteMove(models.Model):
    _name = "waste.move"

    name = fields.Char(string='Waste Move',)

    transport_type = fields.Many2one('waste.transport.type', string='Transport Type')
    recipient_partner = fields.Many2one('res.partner', string='Recipient Partner')
    origin_partner = fields.Many2one('res.partner', string='Origin Partner')

    recipient_installation = fields.Many2one('waste.treatment.installation', string='Recipient Installation')
    origin_installation = fields.Many2one('waste.treatment.installation', string='Origin Installation')
    recipient_site = fields.Many2one('waste.treatment.site', string='Recipient Site')
    origin_site = fields.Many2one('waste.treatment.site', string='Origin Site')

    abfallart = fields.Many2one('waste.type', "Abfallart")
    amount = fields.Float(string='Transferred amount')

    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'), ('approved', 'Approved')],
        'Status', copy=False, default='draft', index=True)

    def action_show_dialog(self):
        return {'type': 'ir.actions.act_window',
                'name': _('Abfallbilanz'),
                'res_model': 'waste.bilanz',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_user_id': self.id}, }
    def approve_move(self):
        self.state = 'approved'