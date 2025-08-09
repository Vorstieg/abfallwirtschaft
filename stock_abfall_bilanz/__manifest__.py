# -*- coding: utf-8 -*-
{
    'name': 'Abfallbilanz',

    'summary': 'Used to generate the Abfallbilanz',
    'description': """
        This module allows users to create XML files that are required for Abfallbilanz in Austria.
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",

    'category': 'Inventory',
    'version': '0.1',
    'license': 'LGPL-3',

    'depends': ['base', 'stock','product_waste_registry'],
    'data': [
        "views/waste_transport_views.xml",
        'security/ir.model.access.csv',
        "data/waste_quantification_type.xml",
        "data/waste_transport_types.xml",
        "data/waste_recycling_types.xml",
        "data/waste_origin_types.xml",
        "views/waste_quantification_type.xml",
        "views/waste_recycling_type_views.xml",
        "views/waste_treatment_installation.xml",
        "views/waste_move.xml",
    ],
}
