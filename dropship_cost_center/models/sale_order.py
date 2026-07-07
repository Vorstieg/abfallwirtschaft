from odoo import fields, models

from .analytic_distribution import merge_analytic_distribution


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    dropship_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Dropship Cost Center',
        copy=False,
        readonly=True,
    )

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order._has_dropship_cost_center_lines():
                order._get_or_create_dropship_analytic_account()
        return res

    def _has_dropship_cost_center_lines(self):
        self.ensure_one()
        return any(line._is_dropship_cost_center_line() for line in self.order_line)

    def _get_or_create_dropship_analytic_account(self):
        self.ensure_one()
        if self.dropship_analytic_account_id:
            return self.dropship_analytic_account_id

        plan = self.env.ref('dropship_cost_center.analytic_plan_streckengeschaeft')
        account = self.env['account.analytic.account'].sudo().create({
            'name': self.name,
            'code': self.name,
            'plan_id': plan.id,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
        })
        self.sudo().dropship_analytic_account_id = account.id
        return account


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
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
        if not self._is_dropship_cost_center_line():
            return self.env['account.analytic.account']
        return self.order_id._get_or_create_dropship_analytic_account()

    def _is_dropship_cost_center_line(self):
        self.ensure_one()
        if self.display_type:
            return False

        route = self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False)
        route_ids = self.route_ids | self.product_id.route_ids | self.product_id.categ_id.total_route_ids
        if route and route in route_ids:
            return True

        if self.purchase_line_ids.filtered(lambda line: line._is_dropshipped()):
            return True

        return bool(self.move_ids.filtered(lambda move: move.is_dropship or move.picking_type_id.code == 'dropship'))
