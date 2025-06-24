import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
import datetime

# --- Configuration ---
# The name of the custom CSV file.
# Make sure this file is in the same directory as this script.
CSV_FILENAME = 'waste_types_export.csv'
# The name of the XML file that will be generated.
OUTPUT_XML_FILENAME = 'waste_type_data.xml'
# The technical name of the Odoo model.
MODEL_NAME = 'waste.type'
# A prefix for the XML record IDs to ensure they are unique.
ID_PREFIX = 'waste_type'
# ---------------------

def is_date_range_valid(start_str, end_str, today):
    """
    Checks if today's date is within the given start and end date strings.
    An empty start or end date means that boundary is open.
    Returns True if the range is valid or if no dates are provided.
    """
    if not start_str and not end_str:
        return True # No date restriction

    try:
        start_date = datetime.datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else None
        end_date = datetime.datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else None

        if start_date and today < start_date:
            return False # Not started yet
        if end_date and today > end_date:
            return False # Already expired
        
        return True
    except ValueError:
        # If date parsing fails, treat it as an invalid range
        print(f"Warning: Could not parse date range '{start_str}' - '{end_str}'. Skipping.")
        return False


def generate_xml_from_custom_csv():
    """
    Reads the specified fixed-format CSV and generates an Odoo-compatible XML file.
    """
    today = datetime.date.today()
    print(f"Using current date for validation: {today.strftime('%Y-%m-%d')}")

    try:
        with open(CSV_FILENAME, mode='r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',', quotechar='"', escapechar='\\')

            # Create the root elements for the Odoo XML file
            odoo_node = ET.Element('odoo')
            data_node = ET.SubElement(odoo_node, 'data', {'noupdate': '1'})

            print(f"Reading from '{CSV_FILENAME}'...")

            record_count = 0
            for i, row in enumerate(csv_reader):
                if len(row) < 13:
                    print(f"Warning: Skipping malformed row {i + 1}. Not enough columns.")
                    continue

                # --- Date Validation ---
                is_valid1 = is_date_range_valid(row[0], row[1], today)
                is_valid2 = is_date_range_valid(row[11], row[12], today)

                if not is_valid1 or not is_valid2:
                    # Skip the row if the current date is outside either of the date ranges
                    continue

                # --- Field Mapping (based on column index) ---
                # NOTE: Add a 'note' field (fields.Text) to your 'waste.type' model in Odoo
                # for the 'test' value to be imported.
                field_map = {
                    'gtin': row[2],
                    'key_number': row[3],
                    'specification_enumeration': row[4],
                    'dangerous': row[5],
                    'name': row[6],
                    'specification': row[7],
                    'note': row[10], # Assuming you have a 'note' field
                }

                # --- External ID Generation ---
                key_number = row[3].strip()
                dangerous_flag = row[5].strip()

                if not key_number:
                    print(f"Warning: Skipping row {i + 1} as it's missing a key_number required for the ID.")
                    continue

                record_id = f"{key_number}{dangerous_flag}"

                # Create the <record> element
                record_node = ET.SubElement(data_node, 'record', {'id': record_id, 'model': MODEL_NAME})

                # Create a <field> element for each mapped field
                for field_name, value in field_map.items():
                    if value and value.strip(): # Only create a tag if the value is not empty
                        field_node = ET.SubElement(record_node, 'field', {'name': field_name})
                        field_node.text = value.strip()

                record_count += 1

            # Create a nicely formatted string from the XML tree
            xml_string = ET.tostring(odoo_node, 'utf-8')
            reparsed = minidom.parseString(xml_string)
            pretty_xml_string = reparsed.toprettyxml(indent="    ", encoding='utf-8')

            # Write the formatted XML to the output file
            with open(OUTPUT_XML_FILENAME, 'wb') as xml_file:
                xml_file.write(pretty_xml_string)

            print(f"\nSuccessfully generated '{OUTPUT_XML_FILENAME}' with {record_count} valid records.")
            print("You can now copy this file to your module's 'data' directory.")

    except FileNotFoundError:
        print(f"\nERROR: The file '{CSV_FILENAME}' was not found.")
        print("Please make sure you have exported your data and named the file correctly.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == '__main__':
    generate_xml_from_custom_csv()
