from odoo import models, fields

class WasteRecyclingType(models.Model):
    _name = "waste.recycling.type"
    _description = "Waste Recycling Types"

    gtin = fields.Char(string='GTIN')
    rdp_code = fields.Char(string='R/D/P Code', required=True)
    description = fields.Char(string='Beschreibung', help="General description of the waste type.")
    detailed_description = fields.Char(string='Detailbeschreibung', help="Detailed description of the waste type.")

class WasteOriginType(models.Model):
    _name = "waste.origin.type"
    _description = "Waste Origin Types"

    gtin = fields.Char(string='GTIN', help="Global Trade Item Number.")
    rdp_code = fields.Char(string='R/D/P Code')
    description = fields.Char(string='Beschreibung')
    detailed_description = fields.Char(string='Detailbeschreibung')
    notes = fields.Char(string='Notizen')
    hint = fields.Char(string='Hint')