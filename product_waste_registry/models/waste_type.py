import logging
from odoo import api, fields, models
from odoo.osv import expression

_logger = logging.getLogger(__name__)

class WasteType(models.Model):
    _name = 'waste.type'
    _description = 'Waste Type'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    specification = fields.Char(string='Specification', translate=True)
    specification_enumeration = fields.Char(string='Specification Enumeration', translate=True)
    dangerous = fields.Char(string='Dangerous', translate=True)
    gtin = fields.Char(string='GTIN', help='Global Trade Item Number', index=True, translate=True)
    key_number = fields.Char(string='Key Number', index=True, translate=True)
    note = fields.Char(string='Note', index=True, translate=True)

    def _compute_display_name(self):
        """
        Overrides the default name_get to display both the name and specification
        in Many2one dropdowns.
        """
        for record in self:
            name = record.name
            if record.specification:
                # Format the name as "Name (Specification)" if specification exists
                name += f" ({record.specification})"
            if record.dangerous:
                # Format the name as "Name (Specification)" if specification exists
                name += f" [{record.dangerous}]"
            record.display_name = name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """
        Provides a more powerful search capability by allowing to search by GTIN an key number
        """
        args = list(args or [])
        domain = [('display_name', operator, name)]

        # If the search term is a number, add numeric fields to the search
        if name.isdigit():
            domain = expression.OR([
                domain,
                [('key_number', '=', name)],
                [('gtin', '=', name)]
            ])

        # Combine the custom domain with any existing arguments using AND logic
        full_domain = expression.AND([args, domain])

        records = self.search(full_domain, limit=limit)
        return [(record.id, record.display_name) for record in records]
