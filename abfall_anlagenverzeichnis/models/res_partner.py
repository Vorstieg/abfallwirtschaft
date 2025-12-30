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
        inverse_name='partner_id', string='Waste Treatment Sites', )
    person_gln = fields.Char(string='Person GLN')

    @api.constrains('person_gln')
    def _check_person_gln(self):
        for record in self:
            if record.person_gln:
                try:
                    ean.validate(self.person_gln)
                except (InvalidChecksum, InvalidFormat, InvalidLength):
                    raise ValidationError("The person GLN is not valid")

    def _get_eras_entity_data(self):
        """
        Queries eRAS for the partner's GLN and returns the matching entity and full response data.
        Returns: (target_entity, env_data)
        """
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
            return None, None

        env_data = response.EnvironmentalData

        target_entity = None
        target_scope_id = None

        # Check both Person and Organization lists
        entities = getattr(env_data, 'Person', []) + getattr(env_data, 'Organization', [])

        for entity in entities:
            if self._match_gln(entity.ID, self.person_gln):
                target_entity = entity
                break

        if not target_entity:
            # Collect found IDs for debugging
            found_ids = [
                self._get_ident_value(ident)
                for entity in entities
                for ident in getattr(entity, 'ID', [])
            ]
            raise UserError(_("No entity found in eRAS for GLN %s. Found IDs in response: %s") % (
                self.person_gln, ", ".join(filter(None, found_ids))))

        return target_entity, env_data

    def action_query_eras(self):
        target_entity, env_data = self._get_eras_entity_data()
        if not target_entity:
            return

        self._process_eras_sites(target_entity, env_data)

    def action_update_eras_details(self):
        """
        Queries eRAS, updates the partner name from the result, and updates sites.
        """
        target_entity, env_data = self._get_eras_entity_data()
        if not target_entity:
            return

        # Update Name
        new_name = getattr(target_entity, 'Name', None)
        if new_name:
            self.name = str(new_name)

        self._process_eras_sites(target_entity, env_data)

    def _process_eras_sites(self, target_entity, env_data):
        """
        Updates sites based on the found entity and environment data.
        """
        target_scope_id = getattr(target_entity, 'DocumentScopeAssignmentID', None)

        # Find LocalUnits that reference this entity
        local_units = []
        all_local_units = getattr(env_data, 'LocalUnit', [])

        for lu in all_local_units:
            refs = getattr(lu, 'AssociatedObjectDocumentScopeReferenceID', [])
            # Check if any reference matches the target scope ID
            if any(self._get_ident_value(ref) == target_scope_id for ref in refs):
                local_units.append(lu)

        self._update_sites_from_local_units(local_units)

    def _get_val(self, obj, key, default=None):
        """ Helper to get value from dict or object """
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _get_ident_value(self, ident):
        """ Helper to extract value from identifier object/dict """
        if isinstance(ident, dict):
            return ident.get('_value_1') or ident.get('value')
        return getattr(ident, '_value_1', None) or getattr(ident, 'value', None) or str(ident)

    def _extract_gln(self, identifiers):
        """ Extract the first 13-digit GLN from a list of identifiers """
        if not identifiers:
            return None
        return next((
            self._get_ident_value(ident)
            for ident in identifiers
            if len(self._get_ident_value(ident) or '') == 13
        ), None)

    def _extract_address(self, entity):
        """ Extract address dictionary from entity """
        address_data = {}
        addresses = self._get_val(entity, 'Address', [])
        if addresses:
            # Take the first address
            # Address is a list of dicts/objects
            addr = addresses[0] if isinstance(addresses, list) else addresses
            components = self._get_val(addr, 'Component', [])
            
            street_name = ""
            street_number = ""
            zip_code = ""
            city = ""
            country_code = ""

            for comp in components:
                type_id = self._get_val(comp, 'TypeID', {})
                obj_designation = self._get_val(type_id, 'objectDesignation', '')
                
                # Try to find the value in different places
                val = self._get_val(comp, 'RepresentationDesignation')
                
                if not val:
                    rep_id = self._get_val(comp, 'RepresentationID')
                    if rep_id:
                        val = self._get_ident_value(rep_id)
                
                if not val:
                    # Fallback for City/Country which might be in ID
                    comp_id = self._get_val(comp, 'ID')
                    if comp_id:
                            if obj_designation == 'Land':
                                val = self._get_ident_value(comp_id)
                            else:
                                # For City, sometimes the name is in objectDesignation of the ID
                                val = self._get_val(comp_id, 'objectDesignation')

                if obj_designation == 'Straße':
                    street_name = val
                elif obj_designation == 'Haus (Hausnummer)':
                    street_number = val
                elif obj_designation == 'Postgebiet (Postleitzahl)':
                    zip_code = val
                elif obj_designation == 'Ort':
                    city = val
                elif obj_designation == 'Land':
                    country_code = val

            return {
                'street': f"{street_name} {street_number}".strip(),
                'zip': zip_code,
                'city': city,
                'country_code': country_code,
            }

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
            lu_gln = self._extract_gln(getattr(local_unit, 'ID', []))
            
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

    def search_eras_by_name(self, name):
        config = self.env['ir.config_parameter'].sudo()
        user = config.get_param('abfallwirtschaft.eras_api_user')
        password = config.get_param('abfallwirtschaft.eras_api_password')
        base_url = config.get_param('abfallwirtschaft.eras_base_url')

        if not user or not password:
            return []

        client = ErasClient(user, password, base_url=base_url)

        try:
            response = client.query_register({'personenName': name})
        except Exception as e:
            _logger.error(f"eRAS name search failed: {e}")
            return []

        if not response or not hasattr(response, 'EnvironmentalData'):
            return []

        env_data = response.EnvironmentalData
        results = []

        # Combine Person and Organization results
        entities = getattr(env_data, 'Person', []) + getattr(env_data, 'Organization', [])

        for entity in entities:
            # Extract GLN
            gln = self._extract_gln(self._get_val(entity, 'ID', []))

            if not gln:
                continue

            entity_name = str(self._get_val(entity, 'Name', 'Unknown'))

            # Extract Address
            address_data = self._extract_address(entity)

            results.insert(0, {
                'label': f"{entity_name} ({gln})",
                'value': gln,
                'name': entity_name,
                'gln': gln,
                'address': address_data,
                'phone':''
            })

        return results

    @api.model
    def autocomplete_by_name(self, query, query_country_id, timeout=15):
        # Get standard results (if any)
        results = []
        if hasattr(super(), 'autocomplete_by_name'):
            results = super().autocomplete_by_name(query, query_country_id, timeout=15) or []

        # Get eRAS results
        eras_results = self.search_eras_by_name(query)

        for res in eras_results:
            # Map eRAS result to the format expected by partner_autocomplete
            # We try to provide as much info as possible.
            # The JS widget usually maps keys to field names.

            address = res.get('address', {})

            item = {
                'label': res.get('label'),
                'value': res.get('name'),
                'name': res.get('name'),
                'email': res.get('email'),
                'phone': res.get('phone'),
                'website': res.get('website'),
                'person_gln': res.get('gln'),  # Custom field
                'street': address.get('street'),
                'zip': address.get('zip'),
                'city': address.get('city'),
                # We can also provide a description or sublabel
                'description': f"GLN: {res.get('gln')}",
            }

            # Add to results
            results.insert(0, item)

        return results
