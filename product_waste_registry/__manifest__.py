# -*- coding: utf-8 -*-
{
    'name': "Waste Registry",
    'summary': """
        Adds a model to manage different types of waste and links them to products.""",
    'description': """
        This module introduces a new data model for managing 'Waste Types' and adds a 'Waste Type' field to the product form.
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",

    'category': 'Sales',
    'version': '0.1',
    'license': 'LGPL-3',
    'images': ['images/registrierkasse_thumbnail.png'],

    'depends': ['base', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/waste_type_data.xml',
        'views/waste_type_views.xml',
        'views/product_template_views.xml',
    ],
}
