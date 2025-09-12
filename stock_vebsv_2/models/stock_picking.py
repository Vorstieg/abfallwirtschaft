from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    begleitscheine = fields.One2many('waste.begleitschein', 'stock_picking_id', string='Begleitscheine',
                                     copy=False, )
    begleitschein_recent = fields.Many2one(
        comodel_name='waste.begleitschein',
        string='Most Recent Begleitschein',
        compute='_compute_recent_begleitschein',
        store=True,
    )

    begleitschein_status = fields.Selection(
        string='Begleitschein Status',
        related='begleitschein_recent.state',
        readonly=True,
    )

    @api.depends('begleitscheine')
    def _compute_recent_begleitschein(self):
        for picking in self:
            picking.begleitschein_recent = self.env['waste.begleitschein'].search(
                [('stock_picking_id', '=', picking.id)], order='create_date desc', limit=1)

    def create_begleitschein_action(self):
        if not self._get_waste_products():
            raise UserError(_("You need waste products to create a Begleitschein"))

        if self.picking_type_code == 'outgoing':
            source_partner, target_partner = self.company_id.partner_id, self.partner_id
        elif self.picking_type_code == 'incoming':
            source_partner, target_partner = self.partner_id, self.company_id.partner_id
        elif self.picking_type_code == 'dropship':
            source_partner, target_partner = self.purchase_id.partner_id, self.purchase_id.dest_address_id
        else:
            raise UserError(_("This picking type is not supported."))

        source_sites = self.env['waste.treatment.site'].search([('partner_id', '=', source_partner.id)])
        target_sites = self.env['waste.treatment.site'].search([('partner_id', '=', target_partner.id)])

        if len(source_sites) == 1 and len(target_sites) == 1:
            self.create_begleitschein(source_partner, target_partner, source_sites, target_sites)
        else:
            return {'type': 'ir.actions.act_window',
                    'name': _('Begleitschein'),
                    'res_model': 'begleitschein.modal',
                    'target': 'new',
                    'view_mode': 'form',
                    'context': {'default_stock_picking_id': self.id,
                                'default_source_partner_id': source_partner.id,
                                'default_target_partner_id': target_partner.id,
                                **({'default_source_site': source_sites.id} if len(source_sites) == 1 else {}),
                                **({'default_target_site': target_sites.id} if len(target_sites) == 1 else {})}
                    }

    def _get_waste_products(self):
        return self.move_line_ids.filtered(
            lambda l: l.product_id.waste_type_id
        )

    def create_begleitschein(self, source_partner, target_partner, source_site, target_site):

        begleitschein = self.env['waste.begleitschein'].create({
            'name': self.name.replace("/", "_") + '_Begleitschein',
            'stock_picking_id': self.id,
            'source_partner_id': source_partner.id,
            'target_partner_id': target_partner.id,
            'source_site': source_site.id,
            'target_site': target_site.id,
            'company_id': self.company_id.id,
            'transport_partner_id': self.company_id.id,
            'begleitschein_lines': [(0, 0, {
                'product_id': l.product_id.id,
                'abfallart': l.product_id.waste_type_id.id,
                'product_qty': l.quantity,
            }) for l in self._get_waste_products()],
        })

        if self.picking_type_code == 'dropship':
            begleitschein.dropship_partner_id = self.company_id.partner_id.id

        begleitschein.start_begleitschein()

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

    def start_transport(self):
        self.ensure_one()
        if not self.begleitschein_recent:
            raise UserError(_("There is no Begleitschein to start transport for."))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'waste.begleitschein',
            'view_mode': 'form',
            'res_id': self.begleitschein_recent.id,
            'target': 'current',
        }
