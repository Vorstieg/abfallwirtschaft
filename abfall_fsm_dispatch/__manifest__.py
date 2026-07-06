# -*- coding: utf-8 -*-
{
    'name': 'Abfallwirtschaft FSM Dispatch',
    'summary': 'Außendienstaufgaben aus gemischten Dispositionslisten erstellen',
    'description': """
Erstellt gemischte Dispositionslisten für Lagertransfers und je Transfer eine
Außendienstaufgabe, wenn die Dispositionsliste bestätigt oder aktualisiert wird.
    """,
    'author': 'Vorstieg Software FlexCo',
    'website': 'https://abfallwirtschaft.vorstieg.eu',
    'category': 'Inventory',
    'version': '0.1',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'fleet',
        'industry_fsm',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/cleanup_data.xml',
        'views/dispatch_list_views.xml',
        'views/stock_picking_views.xml',
        'views/project_task_views.xml',
    ],
    'installable': True,
    'application': False,
}
