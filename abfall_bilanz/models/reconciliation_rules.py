from odoo import api, fields, models


class SiteRule(models.Model):
    _name = 'reconciliation.site'
    _description = 'Site Reconciliation'

    name = fields.Char(string='Rule Name', required=True)
    priority = fields.Integer(default=10)
    side = fields.Selection([('source', 'Source'), ('target', 'Target'), ('both', 'Both')], 'Side', default='both')

    partner_id = fields.Many2one('res.partner', string='Partner')
    abfallart = fields.Many2one('waste.type', "Abfallart")

    default_site = fields.Many2one('waste.treatment.site', string="Default Site", required=True)


class InstallationRule(models.Model):
    _name = 'reconciliation.installation'
    _description = 'Installation Reconciliation'

    name = fields.Char(string='Rule Name', required=True)
    priority = fields.Integer(default=10)
    side = fields.Selection([('source', 'Source'), ('target', 'Target'), ('both', 'Both')], 'Side', default='both')

    treatment_site = fields.Many2one('waste.treatment.site', string="Default Site")
    abfallart = fields.Many2one('waste.type', "Abfallart")

    default_installation = fields.Many2one('waste.treatment.installation', string="Default Installation", required=True)


class QuantificationTypeRule(models.Model):
    _name = 'reconciliation.quantificationtype'
    _description = 'Quantification Reconciliation'

    name = fields.Char(string='Rule Name', required=True)
    priority = fields.Integer(default=10)

    abfallart = fields.Many2one('waste.type', "Abfallart")

    default_quantification = fields.Many2one('waste.quantification.type', string="Default Quantification", required=True)


class OriginTypeRule(models.Model):
    _name = 'reconciliation.origintype'
    _description = 'Origin type Reconciliation'

    name = fields.Char(string='Rule Name', required=True)
    priority = fields.Integer(default=10)
    side = fields.Selection([('source', 'Source'), ('target', 'Target'), ('both', 'Both')], 'Side', default='both')

    partner_id = fields.Many2one('res.partner', string='Partner')
    abfallart = fields.Many2one('waste.type', "Abfallart")

    origin_type = fields.Many2one('waste.origin.type', string="Origin Type", required=True)

class RecyclingTypeRule(models.Model):
    _name = 'reconciliation.recyclingtype'
    _description = 'Recycling type Reconciliation'

    name = fields.Char(string='Rule Name', required=True)
    priority = fields.Integer(default=10)
    side = fields.Selection([('source', 'Source'), ('target', 'Target'), ('both', 'Both')], 'Side', default='both')

    partner_id = fields.Many2one('res.partner', string='Partner')
    abfallart = fields.Many2one('waste.type', "Abfallart")

    recycling_type = fields.Many2one('waste.recycling.type', string="Recycling Type", required=True)

class TransportTypeRule(models.Model):
    _name = 'reconciliation.transport.type'
    _description = 'Transport type Reconciliation'

    name = fields.Char(string='Rule Name', required=True)
    priority = fields.Integer(default=10)
    side = fields.Selection([('source', 'Source'), ('target', 'Target'), ('both', 'Both')], 'Side', default='both')

    partner_id = fields.Many2one('res.partner', string='Partner')
    abfallart = fields.Many2one('waste.type', "Abfallart")

    transport_type = fields.Many2one('waste.transport.type', string="Transport Type", required=True)
