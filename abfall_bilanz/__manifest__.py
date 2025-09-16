# -*- coding: utf-8 -*-
{
    'name': 'Abfallbilanz',

    'summary': 'Used to generate the Abfallbilanz',
    'description': """
        This module allows users to create XML files that are required for Abfallbilanz in Austria.
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",
    'images': ['images/template.png'],

    'category': 'Inventory',
    'version': '0.1',
    'license': 'LGPL-3',

    'depends': ['base', 'stock','product_waste_registry','product_waste_anlagenverzeichnis'],
    'data': [
        'security/ir.model.access.csv',
        "views/waste_move.xml",
    ],
}
