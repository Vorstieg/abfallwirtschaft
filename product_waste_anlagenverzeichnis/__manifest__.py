# -*- coding: utf-8 -*-
{
    'name': "Waste Processing Registry",
    'summary': """
        Adds a model to manage different types of waste processing cites""",
    'description': """
        This module introduces a new data model for managing 'Waste processing cites'
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",

    'category': 'Sales',
    'version': '0.1',
    'license': 'LGPL-3',

    'depends': ['product','product_waste_registry'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
        'views/waste_treatment_installation.xml',
        'views/res_config_settings_view.xml',
        'data/ir_cron_data.xml',
    ],
}
