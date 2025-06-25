# -*- coding: utf-8 -*-
{
    'name': 'ANV Begleitschein EBSM',

    'summary': 'Generates Begleitschein reports for gefährlichen Abfall according to ANV 2012',
    'description': """
        This module allows users to send Begleitschein for gefährlichen Abfall,
        compliant with the Austrian ANV 2012 regulations to Umweltbundesamt.
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Inventory',
    'version': '0.1',
    'license': 'LGPL-3',

    'depends': ['base', 'stock','product_waste_registry'],
    'data': [
        'views/report_anv_begleitschein.xml',  # Corrected path
    ],
}
