from odoo import models

from .analytic_distribution import merge_analytic_distribution


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move=move)
        account = self._get_dropship_analytic_account()
        if account and not self.display_type:
            res['analytic_distribution'] = merge_analytic_distribution(
                self.env,
                res.get('analytic_distribution') or self.analytic_distribution,
                account,
            )
        return res

    def _get_dropship_analytic_account(self):
        self.ensure_one()
        if not self._is_dropshipped():
            return self.env['account.analytic.account']

        sale_lines = self.sale_line_id | self.move_ids.sale_line_id
        sale_orders = sale_lines.order_id
        if not sale_orders:
            return self.env['account.analytic.account']

        return sale_orders[:1]._get_or_create_dropship_analytic_account()
