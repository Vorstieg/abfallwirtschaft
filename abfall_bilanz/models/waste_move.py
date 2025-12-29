from odoo import models, fields, _

class WasteMove(models.Model):
    _name = "waste.move"
    _description = "Waste Move"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Waste Move',)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    recipient_partner = fields.Many2one('res.partner', string='Recipient Partner', tracking=True)
    origin_partner = fields.Many2one('res.partner', string='Origin Partner', tracking=True)

    recipient_installation = fields.Many2one('waste.treatment.installation', string='Recipient Installation')
    origin_installation = fields.Many2one('waste.treatment.installation', string='Origin Installation')
    recipient_site = fields.Many2one('waste.treatment.site', string='Recipient Site')
    origin_site = fields.Many2one('waste.treatment.site', string='Origin Site')

    recycling_type = fields.Many2one('waste.recycling.type', string='Recycling Type')
    origin_type = fields.Many2one('waste.origin.type', string='Origin Type')
    transport_type = fields.Many2one('waste.transport.type', string='Transport Type')

    abfallart = fields.Many2one('waste.type', "Abfallart", tracking=True)
    amount = fields.Float(string='Transferred amount', tracking=True)
    quantification_type = fields.Many2one('waste.quantification.type', string='Measurement type of waste')

    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'), ('approved', 'Approved')],
        'Status', copy=False, default='draft', tracking=True)

    def approve_move(self):
        self.state = 'approved'