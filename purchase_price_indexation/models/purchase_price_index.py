from odoo import api, fields, models


class PurchasePriceIndex(models.Model):
    _name = 'purchase.price.index'
    _description = 'Purchase Price Index'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        index=True,
    )
    value_ids = fields.One2many('purchase.price.index.value', 'index_id', string='Values')

    _sql_constraints = [
        ('purchase_price_index_code_company_uniq', 'unique(code, company_id)', 'Index code must be unique per company.'),
    ]

    def _get_value_for_date(self, target_date):
        self.ensure_one()
        value_line = self.env['purchase.price.index.value'].search([
            ('index_id', '=', self.id),
            ('date', '<=', target_date),
        ], order='date desc', limit=1)
        return value_line.value if value_line else False


class PurchasePriceIndexValue(models.Model):
    _name = 'purchase.price.index.value'
    _description = 'Purchase Price Index Value'
    _order = 'date desc, id desc'

    index_id = fields.Many2one('purchase.price.index', required=True, ondelete='cascade', index=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    value = fields.Float(required=True, digits=(16, 6))
    company_id = fields.Many2one(related='index_id.company_id', store=True, readonly=True)

    _sql_constraints = [
        ('purchase_price_index_value_positive', 'check(value > 0)', 'Index value must be positive.'),
        ('purchase_price_index_value_unique', 'unique(index_id, date)', 'Only one value per index and date is allowed.'),
    ]
