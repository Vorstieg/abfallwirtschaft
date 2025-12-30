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

    'depends': ['base', 'stock', 'abfall_stammdaten', 'abfall_anlagenverzeichnis', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        "views/waste_move.xml",
        "views/reconciliation_views.xml",
        "views/waste_balance_entries_views.xml",
        'views/waste_bilanz_submission_views.xml',
    ],
    'demo': [
        'demo/abfall_bilanz_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'abfall_bilanz/static/src/xml/waste_sankey.xml',
            'abfall_bilanz/static/src/js/waste_sankey.js',
        ],
    },
}
