import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        if self.picking_type_code == 'outgoing':
            source_partner, target_partner = self.company_id.partner_id, self.partner_id
        elif self.picking_type_code == 'incoming':
            source_partner, target_partner = self.partner_id, self.company_id.partner_id
        else:
            _logger.warning("Unsupported picking type")
            return res

        moves = [self.create_waste_move(move, index, source_partner, target_partner)
                 for index, move in enumerate(self.move_ids.filtered(lambda m: m.state == 'done'))
                 if move.product_id.waste_type_id]

        if moves:
            self.env['waste.move'].create(moves)

        return res

    def create_waste_move(self, move, index, source_partner, target_partner):
        waste_type = move.product_id.waste_type_id
        origin_site = self.get_site(target_partner, 'source', waste_type)
        recipient_site = self.get_site(source_partner, 'target', waste_type)
        origin_installation = self.get_installation(origin_site, "source", waste_type)
        recipient_installation = self.get_installation(recipient_site, "target", waste_type)
        origin_type = self.get_origin_type(source_partner, 'target', waste_type)
        recycling_type = self.get_recycling_type(target_partner, 'target', waste_type)
        transport_type = self.get_transport_type(target_partner, 'target', waste_type)
        quantification_type = self.get_quantification_type(waste_type)

        uom_kg = self.env.ref('uom.product_uom_kgm')
        amount = move.product_qty

        # Check if UoMs share a common reference (can be converted) using Odoo 19's tree structure
        if move.product_uom._has_common_reference(uom_kg):
            amount = move.product_uom._compute_quantity(move.product_qty, uom_kg)

        return {
            'name': f"{self.name} {index}",
            'recipient_partner': target_partner.id,
            'origin_partner': source_partner.id,
            'recipient_installation': recipient_installation.id if recipient_installation else False,
            'origin_installation': origin_installation.id if origin_installation else False,
            'recipient_site': recipient_site.id if recipient_site else False,
            'origin_site': origin_site.id if origin_site else False,
            'recycling_type': recycling_type.id if recycling_type else False,
            'origin_type': origin_type.id if origin_type else False,
            'transport_type': transport_type.id if transport_type else False,
            'abfallart': waste_type.id,
            'amount': amount,
            'quantification_type': quantification_type.id if quantification_type else False,
            'date': move.date,
            'company_id': self.company_id.id,
            'state': 'draft',
        }

    def get_site(self, partner, side, abfallart):
        if not partner:
            return None
        if len(partner.waste_treatment_sites) == 1:
            return partner.waste_treatment_sites

        rule = self.env['reconciliation.site'].search([('side', 'in', [side, 'both']),
                                                       ('partner_id', 'in', [partner.id, False]),
                                                       ('abfallart', 'in', [abfallart.id, False])],
                                                      order='priority asc',
                                                      limit=1)
        if rule:
            return rule.default_site

    def get_installation(self, site, side, abfallart):
        if not site:
            return None
        if len(site.treatment_installations) == 1:
            return site.treatment_installations

        rule = self.env['reconciliation.installation'].search([('side', 'in', [side, 'both']),
                                                               ('treatment_site', 'in', [site.id, False]),
                                                               ('abfallart', 'in', [abfallart.id, False])],
                                                              order='priority asc',
                                                              limit=1)
        if rule:
            return rule.default_installation

    def get_origin_type(self, partner_id, side, abfallart):
        rule = self.env['reconciliation.origintype'].search([('side', 'in', [side, 'both']),
                                                             ('partner_id', 'in', [partner_id.id, False]),
                                                             ('abfallart', 'in', [abfallart.id, False])],
                                                            order='priority asc',
                                                            limit=1)
        if rule:
            return rule.origin_type

    def get_recycling_type(self, partner_id, side, abfallart):
        rule = self.env['reconciliation.recyclingtype'].search([('side', 'in', [side, 'both']),
                                                                ('partner_id', 'in', [partner_id.id, False]),
                                                                ('abfallart', 'in', [abfallart.id, False])],
                                                               order='priority asc',
                                                               limit=1)
        if rule:
            return rule.recycling_type

    def get_transport_type(self, partner_id, side, abfallart):
        rule = self.env['reconciliation.transport.type'].search([('side', 'in', [side, 'both']),
                                                                ('partner_id', 'in', [partner_id.id, False]),
                                                                ('abfallart', 'in', [abfallart.id, False])],
                                                               order='priority asc',
                                                               limit=1)
        if rule:
            return rule.transport_type

    def get_quantification_type(self, abfallart):
        rule = self.env['reconciliation.quantificationtype'].search([('abfallart', 'in', [abfallart.id, False])],
                                                                    order='priority asc',
                                                                    limit=1)
        if rule:
            return rule.default_quantification
