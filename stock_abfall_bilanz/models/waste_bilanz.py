from odoo import api, fields, models, _
from datetime import datetime, timedelta

class WasteBilanz(models.TransientModel):
    _name = 'waste.bilanz'
    _description = 'Point of Sale Details Report'

    def _get_year_selection(self):
        current_year = datetime.now().year
        year_list = []
        for year in range(current_year - 10, current_year + 11):
            year_list.append((str(year), str(year)))
        return year_list

    year = fields.Selection(
        selection=_get_year_selection,
        string='Year',
        default=str(datetime.now().year),
        required=True
    )

    def action_download_bilanz(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/download/abfallwirtschaft/{self.year}',
            'target': 'self',
        }