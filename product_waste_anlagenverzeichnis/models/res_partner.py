from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from ..utils.eras_client import ErasClient

from stdnum import ean
from stdnum.exceptions import InvalidChecksum, InvalidFormat, InvalidLength

import logging
_logger = logging.getLogger(__name__)

class Partner(models.Model):
    _inherit = 'res.partner'

    waste_treatment_sites = fields.One2many(
        comodel_name='waste.treatment.site',
        inverse_name='partner_id', string='Waste Treatment Sites',)
    person_gln = fields.Char(string='Person GLN')

    @api.constrains('person_gln')
    def _check_person_gln(self):
        for record in self:
            if record.person_gln:
                try:
                    ean.validate(self.person_gln)
                except (InvalidChecksum, InvalidFormat, InvalidLength):
                    raise ValidationError("The person GLN is not valid")

    def action_query_eras(self):
        self.ensure_one()
        if not self.person_gln:
            raise UserError(_("Please set a Person GLN first."))

        # Credentials from ir.config_parameter
        config = self.env['ir.config_parameter'].sudo()
        user = config.get_param('abfallwirtschaft.eras_api_user')
        password = config.get_param('abfallwirtschaft.eras_api_password')
        base_url = config.get_param('abfallwirtschaft.eras_base_url')

        if not user or not password:
            raise UserError(_("Please configure eRAS credentials in General Settings."))

        client = ErasClient(user, password, base_url=base_url)
        
        try:
            response = client.query_register({'gln': self.person_gln})
        except Exception as e:
            raise UserError(_("eRAS Query failed: %s") % str(e))

        if not response or not hasattr(response, 'EnvironmentalData'):
            return

        env_data = response.EnvironmentalData
        
        target_entity = None
        target_scope_id = None
        
        # Check both Person and Organization lists
        entities = getattr(env_data, 'Person', []) + getattr(env_data, 'Organization', [])
        
        for entity in entities:
            if self._match_gln(entity.ID, self.person_gln):
                target_entity = entity
                target_scope_id = getattr(entity, 'DocumentScopeAssignmentID', None)
                break
        
        if target_entity:
            # Find LocalUnits that reference this entity
            local_units = []
            all_local_units = getattr(env_data, 'LocalUnit', [])
            
            for lu in all_local_units:
                refs = getattr(lu, 'AssociatedObjectDocumentScopeReferenceID', [])
                # Check if any reference matches the target scope ID
                if any(self._get_ident_value(ref) == target_scope_id for ref in refs):
                    local_units.append(lu)
            
            self._update_sites_from_local_units(local_units)
        else:
            # Collect found IDs for debugging
            found_ids = [
                self._get_ident_value(ident) 
                for entity in entities 
                for ident in getattr(entity, 'ID', [])
            ]
            
            raise UserError(_("No entity found in eRAS for GLN %s. Found IDs in response: %s") % (self.person_gln, ", ".join(filter(None, found_ids))))

    def _get_ident_value(self, ident):
        """ Helper to extract value from identifier object/dict """
        if isinstance(ident, dict):
            return ident.get('_value_1') or ident.get('value')
        return getattr(ident, '_value_1', None) or getattr(ident, 'value', None) or str(ident)

    def _match_gln(self, identifiers, gln):
        """ Check if any identifier matches the GLN """
        if not identifiers:
            return False
        return any(self._get_ident_value(ident) == gln for ident in identifiers)

    def _update_sites_from_local_units(self, local_units):
        """ Update waste.treatment.site records from list of LocalUnits """
        if not local_units:
            return

        Site = self.env['waste.treatment.site']
        
        for local_unit in local_units:
            # Extract GLN
            lu_gln = next((
                self._get_ident_value(ident) 
                for ident in getattr(local_unit, 'ID', []) 
                if len(self._get_ident_value(ident) or '') == 13
            ), None)
            
            if not lu_gln:
                continue

            # Extract Name
            name = str(getattr(local_unit, 'Name', "Unknown Site"))
            
            # Create or Update
            site = Site.search([('gtin', '=', lu_gln), ('partner_id', '=', self.id)], limit=1)
            if site:
                site.name = name
            else:
                Site.create({
                    'gtin': lu_gln,
                    'name': name,
                    'partner_id': self.id,
                })

    @api.model
    def _cron_update_eras_contacts(self):
        """ Scheduled action to update all contacts with a Person GLN from eRAS """
        partners = self.search([('person_gln', '!=', False)])
        for partner in partners:
            try:
                partner.action_query_eras()
                # Commit after each partner to avoid long transaction and partial failures blocking everything?
                # Odoo cron usually runs in one transaction. If one fails, we might want to log and continue.
                # But action_query_eras raises UserError. We should catch it.
                self.env.cr.commit() 
            except Exception as e:
                _logger.error(f"Failed to update eRAS for partner {partner.id} ({partner.name}): {e}")
                self.env.cr.rollback()