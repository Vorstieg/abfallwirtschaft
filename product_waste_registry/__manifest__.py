# -*- coding: utf-8 -*-
{
    'name': "Waste Management",
    'summary': """
        This addon adds core functionality for managing waste in Austria""",
    'description': """
        This module introduces the core data for waste management in Austria.
    """,

    'author': "Vorstieg Software FlexCo",
    'website': "https://abfallwirtschaft.vorstieg.eu",

    'category': 'Sales',
    'version': '0.1',
    'license': 'LGPL-3',
    'images': ['images/template.png'],

    'depends': ['base', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/waste_type_data.xml',
        'data/waste_origin_types.xml',
        'data/waste_quantification_type.xml',
        'data/waste_recycling_types.xml',
        'data/waste_transport_types.xml',
        'data/waste_revocation_reasons.xml',
        'data/waste_contamination_types.xml',
        'views/waste_type_views.xml',
        'views/waste_quantification_type_views.xml',
        'views/waste_recycling_type_views.xml',
        'views/waste_transport_type_views.xml',
        'views/waste_revocation_reason_views.xml',
        'views/waste_contamination_views.xml',
        'views/product_template_views.xml',
		'views/waste_menu_views.xml',
],
}
