from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    begleitscheine = fields.One2many('waste.begleitschein', 'purchase_order_id', string='Begleitscheine',
                                     copy=False, )

    def send_begleitschein(self):
        waste_products = self.order_line.filtered(
            lambda l: l.product_id.waste_type_id
        )

        belgeitschein = self.env['waste.begleitschein'].create({
            'name': self.name + '_Belgeitschein',
            'purchase_order_id': self.id,
            'partner_id': self.partner_id.id,
            'company_partner_id': self.company_id.partner_id.id,
            'begleitschein_lines': [(0, 0, {
                'product_id': l.product_id.id,
                'product_qty': l.product_qty,
            }) for l in waste_products],
        })

        belgeitschein.start_begleitschein()

    def action_view_begleitscheine(self):
        self.ensure_one()
        action = self.env.ref('stock_vebsv_2.action_waste_begleitschein').read()[0]

        begleitschein_count = len(self.begleitscheine)
        if begleitschein_count > 1:
            action['domain'] = [('id', 'in', self.begleitscheine.ids)]
        elif begleitschein_count == 1:
            res = self.env.ref('stock_vebsv_2.view_waste_begleitschein_form', False)
            action['views'] = [(res and res.id or False, 'form')]
            action['res_id'] = self.begleitscheine.id
        else:
            action['domain'] = [('purchase_order_id', '=', self.id)]

        return action
