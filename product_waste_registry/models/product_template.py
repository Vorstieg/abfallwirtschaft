from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    waste_type_id = fields.Many2one(
        'waste.type',
        string='Waste Type',
        index=True,
        help="Weisen Sie diesem Produkt eine Abfallart zu. (Sie können nach Namen suchen oder eine vollständige GTIN oder Schlüsselnummer eingeben)"
    )