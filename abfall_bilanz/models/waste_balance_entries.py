from odoo import models, fields, api

class WasteStorageState(models.Model):
    _name = 'waste.storage.state'
    _description = 'Waste Storage State (Lagerstand)'

    installation_id = fields.Many2one('waste.treatment.installation', string='Installation', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    reporting_date = fields.Date(string='Reporting Date', default=fields.Date.context_today, required=True)
    abfallart = fields.Many2one('waste.type', string='Waste Type')
    amount = fields.Float(string='Amount (kg)', required=True)
    quantification_type = fields.Many2one('waste.quantification.type', string='Quantification Type', required=True)
    buffer_type_code = fields.Char(string='Buffer Type Code', help='GTIN for buffer storage if applicable')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved')
    ], string='Status', default='draft', required=True)

    def action_approve(self):
        self.write({'state': 'approved'})

class WasteStorageCorrection(models.Model):
    _name = 'waste.storage.correction'
    _description = 'Waste Storage Correction (Lagerstandskorrektur)'

    installation_id = fields.Many2one('waste.treatment.installation', string='Installation', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    reporting_date = fields.Date(string='Reporting Date', default=fields.Date.context_today, required=True)
    abfallart = fields.Many2one('waste.type', string='Waste Type', required=True)
    amount = fields.Float(string='Amount (kg)', help="Positive for addition, negative for removal")
    quantification_type = fields.Many2one('waste.quantification.type', string='Quantification Type', required=True)

class WasteReclassification(models.Model):
    _name = 'waste.reclassification'
    _description = 'Waste Reclassification (Abfallartenneuzuordnung)'

    installation_id = fields.Many2one('waste.treatment.installation', string='Installation', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    reporting_date = fields.Date(string='Reporting Date', default=fields.Date.context_today)
    
    preliminary_abfallart = fields.Many2one('waste.type', string='Original Waste Type', required=True)
    new_abfallart = fields.Many2one('waste.type', string='New Waste Type', required=True)
    
    amount = fields.Float(string='Amount (kg)', required=True)
    quantification_type = fields.Many2one('waste.quantification.type', string='Quantification Type', required=True)
    reclassification_reason_id = fields.Many2one('waste.reclassification.reason', string='Reason')

class WasteRemainingCapacity(models.Model):
    _name = 'waste.remaining.capacity'
    _description = 'Landfill Remaining Capacity (Deponierestkapazität)'

    installation_id = fields.Many2one('waste.treatment.installation', string='Installation', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    reporting_date = fields.Date(string='Reporting Date', default=fields.Date.context_today, required=True)
    approved_remaining_capacity = fields.Float(string='Approved Remaining Capacity (m³)')
    physical_remaining_capacity = fields.Float(string='Physical Remaining Capacity (m³)')
