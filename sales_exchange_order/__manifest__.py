# -*- coding: utf-8 -*-
{
    'name': 'Exchange Order',

    'summary': 'Extend the sales order view to connect a purchase order',
    'description': """
    Create a combined Sales and Purchase order. Used to combine purchasing of recyclable materials with sale of waste collection services. 
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",

    'category': 'Sales',
    'version': '0.1',
    'license': 'LGPL-3',

    'depends': ['sale_management', 'purchase', 'account','product'],
    'data': [
        'views/exchange_order_views.xml',
    ],
    'installable': True,
    'application': True,
}
