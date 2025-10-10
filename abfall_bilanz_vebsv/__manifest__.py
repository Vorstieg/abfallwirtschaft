{
    'name': "Abfallbilanz Begleitschein vebsv",
    'version': '1.0',
    'summary': 'Glue module to connect abfall_bilanz and stock_vebsv_2.',
    'description': """
        This module provides the necessary business logic to integrate
        the abfall_bilanz and stock_vebsv_2 modules.

        It ensures that data related to waste balancing is correctly
        synchronized with the VEBSV system, providing a seamless workflow.
    """,
    'author': "Vorstieg Software FlexCo",
    'website': "http://abfallwirtschaft.vorstieg.eu",
    'depends': [
        'abfall_bilanz',
        'stock_vebsv_2'
    ],
    'data': [
    ],
    'auto_install': True,
    'installable': True,
    'license': 'LGPL-3',
}