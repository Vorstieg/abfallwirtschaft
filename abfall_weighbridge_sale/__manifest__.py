{
    "name": "Abfall Weighbridge Sale",
    "summary": "Sales-order integration for weighbridge tickets",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "author": "Vorstieg Software FlexCo", "website": "https://abfallwirtschaft.vorstieg.eu", "license": "LGPL-3",
    "depends": ["abfall_weighbridge_stock", "sale_stock"],
    "data": ["views/weighbridge_sale_views.xml", "report/weighbridge_sale_report.xml"],
    "assets": {"web.assets_backend": ["abfall_weighbridge_sale/static/src/kiosk/**/*"]},
    "installable": True,
}
