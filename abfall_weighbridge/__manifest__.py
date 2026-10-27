{
    "name": "Abfall Weighbridge",
    "summary": "Certified SysTec IT3 weighbridge capture",
    "version": "19.0.2.0.0",
    "category": "Operations",
    "author": "Vorstieg Software FlexCo",
    "website": "https://abfallwirtschaft.vorstieg.eu",
    "license": "LGPL-3",
    "depends": ["mail", "product", "web"],
    "data": [
        "security/weighbridge_security.xml",
        "security/ir.model.access.csv",
        "report/weighbridge_ticket_report.xml",
        "views/weighbridge_station_views.xml",
        "views/weighbridge_ticket_views.xml",
        "views/weighbridge_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "abfall_weighbridge/static/src/kiosk/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
