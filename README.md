TBD: needs to be adapted as we create new modules


# Odoo Waste Registry Module (`product_waste_registry`)

This Odoo module provides a system for managing waste types within Odoo, based on the official Austrian waste directory ("Abfallverzeichnis"). It introduces a new "Waste Type" model, links it to products, and includes a tool for importing data directly from the official source.

The primary data source for this module is the [**Abfallverzeichnis from the EDM Portal**](https://www.edm.gv.at/edm_portal/redaList.do?event=changePaging&show=all&seqCode=c2ck5gyutbw7qf&entireLsq=true) provided by the Austrian government.

---

## Features

* **Waste Type Model**: Creates a new model `waste.type` to store detailed information about different waste types. The model includes fields for:
    * Name (`name`)
    * Specification (`specification`)
    * Key Number (`key_number`)
    * GTIN
    * Dangerous Goods Flag (`dangerous`)
    * And more.
* **Product Integration**: Adds a searchable "Waste Type" dropdown to the standard product form, allowing you to link products directly to a specific waste classification.
* **Initial Data Loading**: The module is designed to be populated with the complete list of waste types from the official Austrian Abfallverzeichnis. A Python script is included to convert the official CSV data into the required XML format to load it in Odoo.

---

## Installation & Setup

1.  **Add the Module**: Add the `product_waste_registry` directory to the `addons_path` in your `odoo.conf` file.
2.  **Generate new Data File (only if you need updated data)**:
    * Download the official waste directory as a CSV file from the EDM Portal link above.
    * Save this file as `waste_types_export.csv`.
    * Place it in the same directory as the `convert_csv_to_xml.py` script provided in the `utils` directory.
    * Run the script from your terminal: `python convert_csv_to_xml.py`
    * This will generate a `waste_type_data.xml` file.
    * Move this generated `waste_type_data.xml` file into the `product_waste_registry/data/` directory (replace with existing).
3.  **Install in Odoo**:
    * Restart your Odoo server.
    * Navigate to the **Apps** menu in Odoo.
    * Click **Update Apps List**.
    * Search for "Waste Management" and click **Install**.

The module will be installed, and the `waste.type` model will be populated with all the data from your generated XML file.