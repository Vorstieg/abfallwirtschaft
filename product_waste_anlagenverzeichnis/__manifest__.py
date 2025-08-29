# -*- coding: utf-8 -*-
{
    'name': "Waste Registry",
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

    'depends': ['base', 'product','product_waste_registry'],
    'data': [
        'security/ir.model.access.csv',
        'views/waste_treatment_installation.xml',
    ],
}
