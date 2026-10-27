{
    "name": "Abfall Weighbridge Stock",
    "summary": "Stock processing for completed weighbridge tickets",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "Vorstieg Software FlexCo",
    "website": "https://abfallwirtschaft.vorstieg.eu",
    "license": "LGPL-3",
    "depends": ["abfall_weighbridge", "stock"],
    "data": [
        "data/weighbridge_stock_data.xml",
        "views/weighbridge_stock_views.xml",
        "report/weighbridge_stock_report.xml",
    ],
    "installable": True,
    "post_init_hook": "post_init_hook",
}
