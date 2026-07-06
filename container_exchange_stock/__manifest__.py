# -*- coding: utf-8 -*-
{
    'name': 'Container Exchange Stock',
    'summary': 'Create incoming and outgoing transfers for container exchanges',
    'description': """
Create one incoming and one outgoing inventory transfer from a sales order when
a customer container is exchanged.
    """,
    'author': 'Vorstieg Software FlexCo',
    'website': 'https://abfallwirtschaft.vorstieg.eu',
    'category': 'Inventory',
    'version': '0.1',
    'license': 'LGPL-3',
    'depends': [
        'sale_stock_renting',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/container_exchange_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
