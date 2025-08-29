# -*- coding: utf-8 -*-
{
    'name': 'VEBSV 2 Begleitschein',

    'summary': 'connects to VEBSV 2',
    'description': """
        This module allows users to create and print Begleitschein reports for gefährlichen Abfall,
        compliant with the Austrian ANV 2012 regulations.
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",
    'images': ['images/template.png'],

    'category': 'Inventory',
    'version': '0.1',
    'license': 'LGPL-3',

    'depends': ['base', 'stock', 'partner_identification_gln','product_waste_anlagenverzeichnis', "purchase"],
    'data': [
        'views/report_anv_begleitschein.xml',
        'views/res_config_settings_views.xml',
        'views/begleitschein_views.xml',
        'views/ir.cron.xml',
        'security/ir.model.access.csv',
    ],
}
