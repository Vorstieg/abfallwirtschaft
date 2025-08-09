from lxml import etree
from datetime import date
from typing import Optional, List, Dict, Any

# Define the XML Namespace
NAMESPACE = "http://edm.gv.at/schema/WasteBalanceInterfaceV2"
NSMAP = {None: NAMESPACE}

SOFTWARE_NAME = "Vorstieg"
SOFTWARE_VERSION = "1.0"
SOFTWARE_INTERFACE_VERSION = "2.15"
def create_waste_handling_notification_xml(
    notification_type_code: str,
    obligated_party_id: str,
    period_start_date: date,
    period_end_date: date,
    waste_movements: Optional[List[Dict[str, Any]]] = None,
    storage_state_installations: Optional[List[Dict[str, Any]]] = None,
    storage_correction_installations: Optional[List[Dict[str, Any]]] = None,
    waste_reclassification_materials: Optional[List[Dict[str, Any]]] = None,
    remaining_capacity_installations: Optional[List[Dict[str, Any]]] = None,
) -> str:
    root = etree.Element("WasteHandlingNotification", nsmap=NSMAP)

    # Add optional creation software information
    etree.SubElement(root, "CreationSoftwareInterfaceVersionID").text = SOFTWARE_INTERFACE_VERSION
    etree.SubElement(root, "CreationSoftwareName").text = SOFTWARE_NAME
    etree.SubElement(root, "CreationSoftwareVersionID").text = SOFTWARE_VERSION

    # Add SpecifiedNotification
    specified_notification = etree.SubElement(root, "SpecifiedNotification")
    etree.SubElement(specified_notification, "TypeCode").text = notification_type_code

    obligated_party = etree.SubElement(specified_notification, "ObligatedParty")
    etree.SubElement(obligated_party, "ID").text = obligated_party_id

    covered_period = etree.SubElement(specified_notification, "CoveredPeriod")
    etree.SubElement(covered_period, "StartDate").text = period_start_date.isoformat()
    etree.SubElement(covered_period, "EndDate").text = period_end_date.isoformat()

    # Add SpecifiedSinglePeriodWasteHandlingNotification if any entries are provided
    if (waste_movements or storage_state_installations or storage_correction_installations or
            waste_reclassification_materials or remaining_capacity_installations):
        single_period_notification = etree.SubElement(root, "SpecifiedSinglePeriodWasteHandlingNotification")

        # Helper function to add party details
        def _add_party(parent_element, tag_name, party_data: Dict):
            if party_data and 'id' in party_data:
                party_element = etree.SubElement(parent_element, tag_name)
                etree.SubElement(party_element, "ID").text = party_data['id']
                if 'type_code' in party_data and party_data['type_code']:
                    etree.SubElement(party_element, "TypeCode").text = party_data['type_code']
                if 'business_type_code' in party_data and party_data['business_type_code']:
                    etree.SubElement(party_element, "BusinessTypeCode").text = party_data['business_type_code']
                if 'specified_organization' in party_data and party_data['specified_organization'] and 'name' in party_data['specified_organization']:
                    org_elem = etree.SubElement(party_element, "SpecifiedOrganization")
                    etree.SubElement(org_elem, "Name").text = party_data['specified_organization']['name']
                if 'specified_person' in party_data and party_data['specified_person']:
                    person_elem = etree.SubElement(party_element, "SpecifiedPerson")
                    etree.SubElement(person_elem, "GivenName").text = party_data['specified_person']['given_name']
                    etree.SubElement(person_elem, "FamilyName").text = party_data['specified_person']['family_name']
                if 'office_address' in party_data and party_data['office_address']:
                    _add_address(party_element, "OfficeAddress", party_data['office_address'])


        # Helper function to add address details
        def _add_address(parent_element, tag_name, address_data: Dict):
            if address_data:
                address_elem = etree.SubElement(parent_element, tag_name)
                if 'city_name' in address_data and address_data['city_name']:
                    etree.SubElement(address_elem, "CityName").text = address_data['city_name']
                if 'postcode' in address_data and address_data['postcode']:
                    etree.SubElement(address_elem, "Postcode").text = address_data['postcode']
                if 'street_name' in address_data and address_data['street_name']:
                    etree.SubElement(address_elem, "StreetName").text = address_data['street_name']
                if 'building_number' in address_data and address_data['building_number']:
                    etree.SubElement(address_elem, "BuildingNumber").text = address_data['building_number']
                if 'room_identification' in address_data and address_data['room_identification']:
                    etree.SubElement(address_elem, "RoomIdentification").text = address_data['room_identification']
                if 'country_sub_division_id' in address_data and address_data['country_sub_division_id']:
                    etree.SubElement(address_elem, "CountrySubDivisionID").text = address_data['country_sub_division_id']
                if 'district_country_sub_division_id' in address_data and address_data['district_country_sub_division_id']:
                    etree.SubElement(address_elem, "DistrictCountrySubDivisionID").text = address_data['district_country_sub_division_id']
                etree.SubElement(address_elem, "CountryID").text = address_data.get('country_id', 'AT') # Default to AT

        # Helper function to add material location details
        def _add_material_location(parent_element, tag_name, location_data: Dict):
            if location_data:
                location_elem = etree.SubElement(parent_element, tag_name)
                if 'description' in location_data and location_data['description']:
                    etree.SubElement(location_elem, "Description").text = location_data['description']
                if 'postal_address' in location_data and location_data['postal_address']:
                    _add_address(location_elem, "PostalAddress", location_data['postal_address'])
                if 'land_areas' in location_data and location_data['land_areas']:
                    for la in location_data['land_areas']:
                        land_area_elem = etree.SubElement(location_elem, "LandArea")
                        etree.SubElement(land_area_elem, "CadastralRegisterMunicipalityID").text = la['cadastral_register_municipality_id']
                        etree.SubElement(land_area_elem, "CadastralRegisterPlotID").text = la['cadastral_register_plot_id']
                if 'specified_installation' in location_data and location_data['specified_installation']:
                    inst_elem = etree.SubElement(location_elem, "SpecifiedInstallation")
                    if 'id' in location_data['specified_installation'] and location_data['specified_installation']['id']:
                        etree.SubElement(inst_elem, "ID").text = location_data['specified_installation']['id']
                    if 'name' in location_data['specified_installation'] and location_data['specified_installation']['name']:
                        etree.SubElement(inst_elem, "Name").text = location_data['specified_installation']['name']
                    if 'location' in location_data['specified_installation'] and location_data['specified_installation']['location']:
                        mobile_loc_elem = etree.SubElement(inst_elem, "Location")
                        stationary_inst_elem = etree.SubElement(mobile_loc_elem, "Installation")
                        if 'id' in location_data['specified_installation']['location']['installation'] and location_data['specified_installation']['location']['installation']['id']:
                            etree.SubElement(stationary_inst_elem, "ID").text = location_data['specified_installation']['location']['installation']['id']
                        if 'name' in location_data['specified_installation']['location']['installation'] and location_data['specified_installation']['location']['installation']['name']:
                            etree.SubElement(stationary_inst_elem, "Name").text = location_data['specified_installation']['location']['installation']['name']

                if 'specified_operating_site' in location_data and location_data['specified_operating_site']:
                    op_site_elem = etree.SubElement(location_elem, "SpecifiedOperatingSite")
                    if 'id' in location_data['specified_operating_site'] and location_data['specified_operating_site']['id']:
                        etree.SubElement(op_site_elem, "ID").text = location_data['specified_operating_site']['id']
                    if 'name' in location_data['specified_operating_site'] and location_data['specified_operating_site']['name']:
                        etree.SubElement(op_site_elem, "Name").text = location_data['specified_operating_site']['name']

        # Helper function to add contamination material
        def _add_contamination_material(parent_element, contamination_materials: List[Dict]):
            if contamination_materials:
                for cm in contamination_materials:
                    cont_mat_elem = etree.SubElement(parent_element, "ContaminationMaterial")
                    etree.SubElement(cont_mat_elem, "ClassificationCode").text = cm['classification_code']
                    if 'description' in cm and cm['description']:
                        etree.SubElement(cont_mat_elem, "Description").text = cm['description']

        # Helper function to add a waste material block (used by StoredWasteMaterialType, SimpleMassMeasurementType, WasteMaterialType)
        def _add_waste_material_details(parent_element, material_data: Dict, is_simple_mass_measurement=False):
            if 'classification_code' in material_data and material_data['classification_code']:
                etree.SubElement(parent_element, "ClassificationCode").text = material_data['classification_code']
            if 'description' in material_data and material_data['description']:
                etree.SubElement(parent_element, "Description").text = material_data['description']

            mass_measurement_tag = "MassMeasurement" if not is_simple_mass_measurement else "SimpleMassMeasurement"
            mass_measurement_elem = etree.SubElement(parent_element, mass_measurement_tag)
            etree.SubElement(mass_measurement_elem, "QuantificationTypeCode").text = material_data['quantification_type_code']
            determined_measure = etree.SubElement(
                mass_measurement_elem, "DeterminedMeasure", unitCode=material_data.get('mass_unit_code', 'KGM')
            )
            determined_measure.text = str(material_data['determined_measure'])

            _add_contamination_material(parent_element, material_data.get('contamination_materials', []))

            if 'fraction_materials' in material_data and material_data['fraction_materials']:
                for fm in material_data['fraction_materials']:
                    fraction_material_elem = etree.SubElement(parent_element, "FractionMaterial")
                    mass_ratio_measure = etree.SubElement(
                        fraction_material_elem, "MassRatioMeasure", unitCode=fm.get('mass_ratio_unit_code', 'P1')
                    )
                    mass_ratio_measure.text = str(fm['mass_ratio_measure'])
                    owner_party = etree.SubElement(fraction_material_elem, "OwnerParty")
                    etree.SubElement(owner_party, "ID").text = fm['owner_party_id']


        # 1. Add WasteMaterialMovement entries
        if waste_movements:
            for movement in waste_movements:
                entry = etree.SubElement(single_period_notification, "SpecifiedWasteHandlingNotificationEntry")
                waste_material_movement = etree.SubElement(entry, "WasteMaterialMovement")

                if 'id' in movement and movement['id']:
                    etree.SubElement(waste_material_movement, "ID").text = movement['id']
                etree.SubElement(waste_material_movement, "TypeCode").text = movement['type_code']
                if 'rejection_indicator' in movement and movement['rejection_indicator'] is not None:
                    etree.SubElement(waste_material_movement, "RejectionIndicator").text = "true" if movement['rejection_indicator'] else "false"

                if 'waste_production_moved_material' in movement and movement['waste_production_moved_material']:
                    prod_moved_mat = etree.SubElement(waste_material_movement, "WasteProductionMovedMaterial")
                    _add_party(prod_moved_mat, "ProductionParty", movement['waste_production_moved_material'].get('production_party'))

                if 'waste_hand_over_moved_material' in movement and movement['waste_hand_over_moved_material']:
                    hand_over_moved_mat = etree.SubElement(waste_material_movement, "WasteHandOverMovedMaterial")
                    _add_party(hand_over_moved_mat, "HandOverParty", movement['waste_hand_over_moved_material'].get('hand_over_party'))
                    _add_material_location(hand_over_moved_mat, "SpecifiedLocation", movement['waste_hand_over_moved_material'].get('location'))
                    if 'origin_physical_process' in movement['waste_hand_over_moved_material'] and movement['waste_hand_over_moved_material']['origin_physical_process']:
                        origin_process = etree.SubElement(hand_over_moved_mat, "OriginPhysicalProcess")
                        if 'type_code' in movement['waste_hand_over_moved_material']['origin_physical_process'] and movement['waste_hand_over_moved_material']['origin_physical_process']['type_code']:
                            etree.SubElement(origin_process, "TypeCode").text = movement['waste_hand_over_moved_material']['origin_physical_process']['type_code']
                        if 'description' in movement['waste_hand_over_moved_material']['origin_physical_process'] and movement['waste_hand_over_moved_material']['origin_physical_process']['description']:
                            etree.SubElement(origin_process, "Description").text = movement['waste_hand_over_moved_material']['origin_physical_process']['description']


                if 'waste_take_over_moved_material' in movement and movement['waste_take_over_moved_material']:
                    take_over_moved_mat = etree.SubElement(waste_material_movement, "WasteTakeOverMovedMaterial")
                    _add_party(take_over_moved_mat, "TakeOverParty", movement['waste_take_over_moved_material'].get('take_over_party'))
                    _add_material_location(take_over_moved_mat, "SpecifiedLocation", movement['waste_take_over_moved_material'].get('location'))
                    if 'designated_treatment_physical_process' in movement['waste_take_over_moved_material'] and movement['waste_take_over_moved_material']['designated_treatment_physical_process']:
                        treatment_process = etree.SubElement(take_over_moved_mat, "DesignatedTreatmentPhysicalProcess")
                        if 'type_code' in movement['waste_take_over_moved_material']['designated_treatment_physical_process'] and movement['waste_take_over_moved_material']['designated_treatment_physical_process']['type_code']:
                            etree.SubElement(treatment_process, "TypeCode").text = movement['waste_take_over_moved_material']['designated_treatment_physical_process']['type_code']
                        if 'description' in movement['waste_take_over_moved_material']['designated_treatment_physical_process'] and movement['waste_take_over_moved_material']['designated_treatment_physical_process']['description']:
                            etree.SubElement(treatment_process, "Description").text = movement['waste_take_over_moved_material']['designated_treatment_physical_process']['description']


                if 'moved_material' in movement and movement['moved_material']:
                    moved_material = etree.SubElement(waste_material_movement, "MovedMaterial")
                    if 'preliminary_classification_waste_material' in movement['moved_material'] and movement['moved_material']['preliminary_classification_waste_material']:
                        prelim_class_waste_mat = etree.SubElement(moved_material, "PreliminaryClassificationWasteMaterial")
                        if 'reclassification_reason_type_code' in movement['moved_material']['preliminary_classification_waste_material'] and movement['moved_material']['preliminary_classification_waste_material']['reclassification_reason_type_code']:
                            etree.SubElement(prelim_class_waste_mat, "ReclassificationReasonTypeCode").text = movement['moved_material']['preliminary_classification_waste_material']['reclassification_reason_type_code']
                        if 'reclassification_reason_description' in movement['moved_material']['preliminary_classification_waste_material'] and movement['moved_material']['preliminary_classification_waste_material']['reclassification_reason_description']:
                            etree.SubElement(prelim_class_waste_mat, "ReclassificationReasonDescription").text = movement['moved_material']['preliminary_classification_waste_material']['reclassification_reason_description']
                        etree.SubElement(prelim_class_waste_mat, "PreliminaryClassificationCode").text = movement['moved_material']['preliminary_classification_waste_material']['preliminary_classification_code']
                        _add_contamination_material(prelim_class_waste_mat, movement['moved_material']['preliminary_classification_waste_material'].get('preliminary_contamination_materials', []))
                        if 'description' in movement['moved_material']['preliminary_classification_waste_material'] and movement['moved_material']['preliminary_classification_waste_material']['description']:
                            etree.SubElement(prelim_class_waste_mat, "Description").text = movement['moved_material']['preliminary_classification_waste_material']['description']

                    _add_waste_material_details(moved_material, movement['moved_material'])

        # 2. Add StorageStateInstallation entries
        if storage_state_installations:
            for storage_state in storage_state_installations:
                entry = etree.SubElement(single_period_notification, "SpecifiedWasteHandlingNotificationEntry")
                storage_state_installation = etree.SubElement(entry, "StorageStateInstallation")

                etree.SubElement(storage_state_installation, "ID").text = storage_state['id']
                if 'buffer_type_code' in storage_state and storage_state['buffer_type_code']:
                    etree.SubElement(storage_state_installation, "BufferTypeCode").text = storage_state['buffer_type_code']

                # Location choice (OperatingSite, PostalAddress, LandArea)
                if 'specified_operating_site' in storage_state and storage_state['specified_operating_site']:
                    op_site_elem = etree.SubElement(storage_state_installation, "SpecifiedOperatingSite")
                    if 'id' in storage_state['specified_operating_site'] and storage_state['specified_operating_site']['id']:
                        etree.SubElement(op_site_elem, "ID").text = storage_state['specified_operating_site']['id']
                    if 'name' in storage_state['specified_operating_site'] and storage_state['specified_operating_site']['name']:
                        etree.SubElement(op_site_elem, "Name").text = storage_state['specified_operating_site']['name']
                elif 'postal_address' in storage_state and storage_state['postal_address']:
                    _add_address(storage_state_installation, "PostalAddress", storage_state['postal_address'])
                elif 'land_areas' in storage_state and storage_state['land_areas']:
                    for la in storage_state['land_areas']:
                        land_area_elem = etree.SubElement(storage_state_installation, "LandArea")
                        etree.SubElement(land_area_elem, "CadastralRegisterMunicipalityID").text = la['cadastral_register_municipality_id']
                        etree.SubElement(land_area_elem, "CadastralRegisterPlotID").text = la['cadastral_register_plot_id']


                if 'description' in storage_state and storage_state['description']:
                    etree.SubElement(storage_state_installation, "Description").text = storage_state['description']
                etree.SubElement(storage_state_installation, "ReportingDate").text = storage_state['reporting_date'].isoformat()

                if 'stored_material' in storage_state and storage_state['stored_material']:
                    stored_material = etree.SubElement(storage_state_installation, "StoredMaterial")
                    _add_waste_material_details(stored_material, storage_state['stored_material'], is_simple_mass_measurement=True)

        # 3. Add StorageCorrectionInstallation entries
        if storage_correction_installations:
            for correction in storage_correction_installations:
                entry = etree.SubElement(single_period_notification, "SpecifiedWasteHandlingNotificationEntry")
                storage_correction_installation = etree.SubElement(entry, "StorageCorrectionInstallation")

                etree.SubElement(storage_correction_installation, "ID").text = correction['id']
                if 'buffer_type_code' in correction and correction['buffer_type_code']:
                    etree.SubElement(storage_correction_installation, "BufferTypeCode").text = correction['buffer_type_code']

                # Location choice (OperatingSite, PostalAddress, LandArea)
                if 'specified_operating_site' in correction and correction['specified_operating_site']:
                    op_site_elem = etree.SubElement(storage_correction_installation, "SpecifiedOperatingSite")
                    if 'id' in correction['specified_operating_site'] and correction['specified_operating_site']['id']:
                        etree.SubElement(op_site_elem, "ID").text = correction['specified_operating_site']['id']
                    if 'name' in correction['specified_operating_site'] and correction['specified_operating_site']['name']:
                        etree.SubElement(op_site_elem, "Name").text = correction['specified_operating_site']['name']
                elif 'postal_address' in correction and correction['postal_address']:
                    _add_address(storage_correction_installation, "PostalAddress", correction['postal_address'])
                elif 'land_areas' in correction and correction['land_areas']:
                    for la in correction['land_areas']:
                        land_area_elem = etree.SubElement(storage_correction_installation, "LandArea")
                        etree.SubElement(land_area_elem, "CadastralRegisterMunicipalityID").text = la['cadastral_register_municipality_id']
                        etree.SubElement(land_area_elem, "CadastralRegisterPlotID").text = la['cadastral_register_plot_id']

                if 'description' in correction and correction['description']:
                    etree.SubElement(storage_correction_installation, "Description").text = correction['description']
                if 'reporting_date' in correction and correction['reporting_date']:
                    etree.SubElement(storage_correction_installation, "ReportingDate").text = correction['reporting_date'].isoformat()

                if 'added_material' in correction and correction['added_material']:
                    added_material = etree.SubElement(storage_correction_installation, "AddedMaterial")
                    _add_waste_material_details(added_material, correction['added_material'], is_simple_mass_measurement=True)
                if 'removed_material' in correction and correction['removed_material']:
                    removed_material = etree.SubElement(storage_correction_installation, "RemovedMaterial")
                    _add_waste_material_details(removed_material, correction['removed_material'], is_simple_mass_measurement=True)

        # 4. Add WasteReclassificationMaterial entries
        if waste_reclassification_materials:
            for reclassification in waste_reclassification_materials:
                entry = etree.SubElement(single_period_notification, "SpecifiedWasteHandlingNotificationEntry")
                waste_reclassification_material = etree.SubElement(entry, "WasteReclassificationMaterial")

                if 'reclassification_reason_type_code' in reclassification and reclassification['reclassification_reason_type_code']:
                    etree.SubElement(waste_reclassification_material, "ReclassificationReasonTypeCode").text = reclassification['reclassification_reason_type_code']
                if 'reclassification_reason_description' in reclassification and reclassification['reclassification_reason_description']:
                    etree.SubElement(waste_reclassification_material, "ReclassificationReasonDescription").text = reclassification['reclassification_reason_description']
                if 'description' in reclassification and reclassification['description']:
                    etree.SubElement(waste_reclassification_material, "Description").text = reclassification['description']
                if 'classification_code' in reclassification and reclassification['classification_code']:
                    etree.SubElement(waste_reclassification_material, "ClassificationCode").text = reclassification['classification_code']
                if 'preliminary_classification_code' in reclassification and reclassification['preliminary_classification_code']:
                    etree.SubElement(waste_reclassification_material, "PreliminaryClassificationCode").text = reclassification['preliminary_classification_code']
                if 'reporting_date' in reclassification and reclassification['reporting_date']:
                    etree.SubElement(waste_reclassification_material, "ReportingDate").text = reclassification['reporting_date'].isoformat()

                mass_measurement_elem = etree.SubElement(waste_reclassification_material, "MassMeasurement")
                etree.SubElement(mass_measurement_elem, "QuantificationTypeCode").text = reclassification['mass_measurement']['quantification_type_code']
                determined_measure = etree.SubElement(
                    mass_measurement_elem, "DeterminedMeasure", unitCode=reclassification['mass_measurement'].get('mass_unit_code', 'KGM')
                )
                determined_measure.text = str(reclassification['mass_measurement']['determined_measure'])

                _add_material_location(waste_reclassification_material, "SpecifiedLocation", reclassification.get('specified_location'))
                _add_contamination_material(waste_reclassification_material, reclassification.get('contamination_materials', []))
                if 'preliminary_contamination_materials' in reclassification and reclassification['preliminary_contamination_materials']:
                    for pcm in reclassification['preliminary_contamination_materials']:
                        prelim_cont_mat_elem = etree.SubElement(waste_reclassification_material, "PreliminaryContaminationMaterial")
                        etree.SubElement(prelim_cont_mat_elem, "ClassificationCode").text = pcm['classification_code']
                        if 'description' in pcm and pcm['description']:
                            etree.SubElement(prelim_cont_mat_elem, "Description").text = pcm['description']

        # 5. Add RemainingCapacityInstallation entries
        if remaining_capacity_installations:
            for capacity in remaining_capacity_installations:
                entry = etree.SubElement(single_period_notification, "SpecifiedWasteHandlingNotificationEntry")
                remaining_capacity_installation = etree.SubElement(entry, "RemainingCapacityInstallation")

                etree.SubElement(remaining_capacity_installation, "ID").text = capacity['id']
                etree.SubElement(remaining_capacity_installation, "ReportingDate").text = capacity['reporting_date'].isoformat()

                if 'approved_remaining_capacity_measure' in capacity and capacity['approved_remaining_capacity_measure']:
                    approved_cap = etree.SubElement(remaining_capacity_installation, "ApprovedRemainingCapacityMeasure",
                                                    unitCode=capacity['approved_remaining_capacity_measure'].get('unit_code', 'MTQ'))
                    approved_cap.text = str(capacity['approved_remaining_capacity_measure']['value'])

                if 'physical_remaining_capacity_measure' in capacity and capacity['physical_remaining_capacity_measure']:
                    physical_cap = etree.SubElement(remaining_capacity_installation, "PhysicalRemainingCapacityMeasure",
                                                    unitCode=capacity['physical_remaining_capacity_measure'].get('unit_code', 'MTQ'))
                    physical_cap.text = str(capacity['physical_remaining_capacity_measure']['value'])

                if 'description' in capacity and capacity['description']:
                    etree.SubElement(remaining_capacity_installation, "Description").text = capacity['description']


    # Return the pretty-printed XML as a string
    return etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True).decode()


if __name__ == "__main__":
    # --- Example Usage ---

    # Example 1: A simple WasteHandlingNotification with just a notification header
    simple_xml = create_waste_handling_notification_xml(
        notification_type_code="JAB",
        obligated_party_id="AT1234567890123",
        period_start_date=date(2024, 1, 1),
        period_end_date=date(2024, 12, 31)
    )
    print("--- Simple WasteHandlingNotification XML ---")
    print(simple_xml)

    # Example 2: WasteHandlingNotification with a WasteMaterialMovement
    waste_movement_data = [
        {
            "type_code": "COLLECTED",
            "waste_hand_over_moved_material": {
                "hand_over_party": {"id": "AT9876543210987", "type_code": "GENERATOR", "specified_organization": {"name": "Test Company GmbH"}},
                "location": {
                    "postal_address": {
                        "street_name": "Main Street",
                        "building_number": "10",
                        "city_name": "Vienna",
                        "postcode": "1010",
                        "country_id": "AT"
                    }
                }
            },
            "waste_take_over_moved_material": {
                "take_over_party": {"id": "AT1122334455667", "type_code": "TREATMENT_FACILITY", "specified_organization": {"name": "Recycling Plant Inc."}},
                "location": {
                    "specified_installation": {
                        "id": "INST001",
                        "name": "Waste Treatment Line A"
                    }
                },
                "designated_treatment_physical_process": {
                    "type_code": "R3",
                    "description": "Recycling of organic materials"
                }
            },
            "moved_material": {
                "classification_code": "200108",  # Biodegradable kitchen and canteen waste
                "description": "Mixed organic waste from households",
                "quantification_type_code": "WEIGHED",
                "determined_measure": 1500.50,
                "mass_unit_code": "KGM",
                "contamination_materials": [
                    {"classification_code": "PLASTIC", "description": "Small plastic bags"}
                ],
                "fraction_materials": [
                    {"mass_ratio_measure": 0.8, "mass_ratio_unit_code": "P1", "owner_party_id": "AT9876543210987"},
                    {"mass_ratio_measure": 0.2, "mass_ratio_unit_code": "P1", "owner_party_id": "AT1122334455667"}
                ]
            }
        }
    ]

    movement_xml = create_waste_handling_notification_xml(
        notification_type_code="JAB",
        obligated_party_id="AT1234567890123",
        period_start_date=date(2024, 1, 1),
        period_end_date=date(2024, 12, 31),
        waste_movements=waste_movement_data
    )
    print("\n--- WasteHandlingNotification XML with WasteMaterialMovement ---")
    print(movement_xml)

    # Example 3: WasteHandlingNotification with a StorageStateInstallation
    storage_state_data = [
        {
            "id": "STORAGE001",
            "buffer_type_code": "INTERIM_STORAGE",
            "reporting_date": date(2024, 12, 31),
            "specified_operating_site": {
                "id": "SITE-VIENNA",
                "name": "Vienna Central Storage"
            },
            "description": "End-of-year inventory of stored hazardous waste",
            "stored_material": {
                "classification_code": "170503*",  # Hazardous waste from construction and demolition
                "description": "Contaminated soil",
                "quantification_type_code": "ESTIMATED",
                "determined_measure": 5000.0,
                "mass_unit_code": "KGM",
                "contamination_materials": [
                    {"classification_code": "ASBESTOS", "description": "Traces of asbestos fibers"}
                ]
            }
        }
    ]

    storage_xml = create_waste_handling_notification_xml(
        notification_type_code="JAB",
        obligated_party_id="AT5556667778889",
        period_start_date=date(2024, 1, 1),
        period_end_date=date(2024, 12, 31),
        storage_state_installations=storage_state_data
    )
    print("\n--- WasteHandlingNotification XML with StorageStateInstallation ---")
    print(storage_xml)

    # Example 4: WasteHandlingNotification with a WasteReclassificationMaterial
    reclassification_data = [
        {
            "reclassification_reason_type_code": "ANALYTICAL_CHANGE",
            "reclassification_reason_description": "New analysis showed different composition.",
            "description": "Reclassified mixed waste",
            "classification_code": "191204",  # Mixed waste from waste treatment
            "preliminary_classification_code": "150106",  # Mixed packaging waste
            "reporting_date": date(2024, 6, 15),
            "mass_measurement": {
                "quantification_type_code": "WEIGHED",
                "determined_measure": 250.75,
                "mass_unit_code": "KGM"
            },
            "specified_location": {
                "postal_address": {
                    "street_name": "Recycling Way",
                    "building_number": "5",
                    "city_name": "Graz",
                    "postcode": "8010",
                    "country_id": "AT"
                }
            },
            "contamination_materials": [{"classification_code": "GLASS", "description": "Broken glass fragments"}],
            "preliminary_contamination_materials": [{"classification_code": "PLASTIC", "description": "Plastic film"}]
        }
    ]

    reclassification_xml = create_waste_handling_notification_xml(
        notification_type_code="JAB",
        obligated_party_id="AT9998887776665",
        period_start_date=date(2024, 1, 1),
        period_end_date=date(2024, 12, 31),
        waste_reclassification_materials=reclassification_data
    )
    print("\n--- WasteHandlingNotification XML with WasteReclassificationMaterial ---")
    print(reclassification_xml)

    # Example 5: WasteHandlingNotification with a RemainingCapacityInstallation
    remaining_capacity_data = [
        {
            "id": "LANDFILL_EAST_ZONE_A",
            "reporting_date": date(2024, 12, 31),
            "approved_remaining_capacity_measure": {
                "value": 100000.0,
                "unit_code": "MTQ"
            },
            "physical_remaining_capacity_measure": {
                "value": 95000.0,
                "unit_code": "MTQ"
            },
            "description": "Remaining capacity for inert waste"
        }
    ]

    remaining_capacity_xml = create_waste_handling_notification_xml(
        notification_type_code="JAB",
        obligated_party_id="AT4443332221110",
        period_start_date=date(2024, 1, 1),
        period_end_date=date(2024, 12, 31),
        remaining_capacity_installations=remaining_capacity_data
    )
    print("\n--- WasteHandlingNotification XML with RemainingCapacityInstallation ---")
    print(remaining_capacity_xml)