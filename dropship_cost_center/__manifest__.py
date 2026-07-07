{
    'name': 'Dropship Cost Center',
    'summary': 'Automatically creates and assigns cost centers for dropshipping',
    'description': """
    Creates an analytic account in the Streckengeschäft plan for dropship sales
    and assigns it to customer invoice and vendor bill lines.
    """,
    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",
    'category': 'Accounting',
    'version': '0.1',
    'license': 'LGPL-3',
    'depends': ['stock_dropshipping', 'account'],
    'data': [
        'data/analytic_plan_data.xml',
    ],
    'installable': True,
    'application': False,
}
