from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    is_indexed_price = fields.Boolean(string='Indexed Price')
    base_price = fields.Float(string='Base Price', digits='Product Price')
    price_index_id = fields.Many2one('purchase.price.index', string='Price Index')
    base_index_value = fields.Float(string='Base Index Value', digits=(16, 6))
    spread = fields.Float(string='Spread', digits='Product Price')

    def _get_indexed_price(self, target_date=False):
        self.ensure_one()
        if not self.is_indexed_price or not self.price_index_id or self.base_index_value <= 0:
            return self.price_unit

        effective_date = target_date or self.requisition_id.date_start or fields.Date.context_today(self)
        current_index_value = self.price_index_id._get_value_for_date(effective_date)
        if not current_index_value:
            return self.price_unit
        return (self.base_price * (current_index_value / self.base_index_value)) + self.spread

    @api.constrains('is_indexed_price', 'price_index_id', 'base_index_value', 'base_price')
    def _check_indexed_pricing_fields(self):
        for line in self:
            if not line.is_indexed_price:
                continue
            if not line.price_index_id:
                raise ValidationError('Price Index is required when Indexed Price is enabled.')
            if line.base_index_value <= 0:
                raise ValidationError('Base Index Value must be greater than zero.')
            if line.base_price <= 0:
                raise ValidationError('Base Price must be greater than zero.')

    @api.depends(
        'product_id',
        'company_id',
        'requisition_id.date_start',
        'product_qty',
        'product_uom_id',
        'requisition_id.vendor_id',
        'requisition_id.requisition_type',
        'is_indexed_price',
        'base_price',
        'price_index_id',
        'base_index_value',
        'spread',
    )
    def _compute_price_unit(self):
        super()._compute_price_unit()

        for line in self:
            if not line.is_indexed_price or not line.price_index_id or line.base_index_value <= 0:
                continue
            line.price_unit = line._get_indexed_price()
