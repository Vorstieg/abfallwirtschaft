{
    "name": "Abfall Weighbridge Purchase",
    "summary": "Purchase-order integration for weighbridge tickets",
    "version": "19.0.1.0.0",
    "category": "Purchases",
    "author": "Vorstieg Software FlexCo", "website": "https://abfallwirtschaft.vorstieg.eu", "license": "LGPL-3",
    "depends": ["abfall_weighbridge_stock", "purchase_stock"],
    "data": ["views/weighbridge_purchase_views.xml", "report/weighbridge_purchase_report.xml"],
    "assets": {"web.assets_backend": ["abfall_weighbridge_purchase/static/src/kiosk/**/*"]},
    "installable": True,
}
