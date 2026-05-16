{
    'name': 'Purchase Price Indexation',
    'summary': 'Dynamic purchase prices based on index values with spread',
    'description': """
Dynamic vendor purchase prices with indexation formula:
price = base_price * (current_index / base_index) + spread.
The indexed price is snapshotted when a new purchase order line is created.
""",
    'author': 'Vorstieg Software FlexCo',
    'website': 'https://abfallwirtschaft.vorstieg.eu',
    'category': 'Purchase',
    'version': '0.1',
    'license': 'LGPL-3',
    'depends': ['purchase_requisition'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_price_index_views.xml',
        'views/purchase_requisition_views.xml',
    ],
}
