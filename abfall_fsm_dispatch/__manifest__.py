# -*- coding: utf-8 -*-
{
    'name': 'Abfallwirtschaft FSM Dispatch',
    'summary': 'Auto-create Field Service jobs from Inventory batches',
    'description': """
Automatically creates one Field Service task per transfer when a stock batch
is created or updated with pickings.
    """,
    'author': 'Vorstieg Software FlexCo',
    'website': 'https://abfallwirtschaft.vorstieg.eu',
    'category': 'Inventory',
    'version': '0.1',
    'license': 'LGPL-3',
    'depends': [
        'stock_picking_batch',
        'industry_fsm',
    ],
    'data': [
        'views/stock_picking_batch_views.xml',
    ],
    'installable': True,
    'application': False,
}
