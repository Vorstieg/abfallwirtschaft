{
    "name": "Abfall Weighbridge Billing",
    "summary": "Immediate and scheduled billing for weighbridge tickets",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Vorstieg Software FlexCo", "website": "https://abfallwirtschaft.vorstieg.eu", "license": "LGPL-3",
    "depends": ["abfall_weighbridge_sale", "abfall_weighbridge_purchase", "account"],
    "data": [
        "security/weighbridge_billing_security.xml", "security/ir.model.access.csv",
        "data/weighbridge_billing_data.xml", "views/weighbridge_billing_views.xml",
        "report/weighbridge_billing_report.xml",
    ],
    "installable": True,
}
