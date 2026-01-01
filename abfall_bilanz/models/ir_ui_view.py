from odoo import fields, models
from odoo.addons.base.models.ir_actions import VIEW_TYPES

# Monkeypatch VIEW_TYPES to allow 'sankey' in validation logic that uses this list
if not any(t[0] == 'sankey' for t in VIEW_TYPES):
    VIEW_TYPES.append(('sankey', 'Sankey'))

class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    type = fields.Selection(selection_add=[('sankey', "Sankey")], ondelete={'sankey': 'cascade'})

    def _get_view_info(self):
        view_info = super()._get_view_info()
        view_info['sankey'] = {
            'icon': 'o_sankey_icon',
            'multi_record': True,
        }
        return view_info

class IrActionsActWindowView(models.Model):
    _inherit = 'ir.actions.act_window.view'

    view_mode = fields.Selection(selection_add=[('sankey', "Sankey")], ondelete={'sankey': 'cascade'})
