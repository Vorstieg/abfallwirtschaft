# -*- coding: utf-8 -*-
{
    'name': 'ANV Begleitschein',

    'summary': 'Generates Begleitschein reports for gefährlichen Abfall according to ANV 2012',
    'description': """
        This module allows users to create and print Begleitschein reports for gefährlichen Abfall,
        compliant with the Austrian ANV 2012 regulations.
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",

    'category': 'Inventory',
    'version': '0.1',
    'license': 'LGPL-3',

    'depends': ['base', 'stock','product_waste_registry'],
    'data': [
        'views/report_anv_begleitschein.xml',  # Corrected path
    ],
}
