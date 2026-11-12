# -*- coding: utf-8 -*-
{
    "name": "Factura electrónica Art Home",
    "summary": "Formato corporativo Art Home para la factura electrónica",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations/EDI",
    "author": "Art Home Textil",
    "license": "LGPL-3",
    "depends": ["l10n_co_bloodo", "account_move_lot"],
    "data": [
        "views/res_company_views.xml",
        "views/product_template_views.xml",
        "reports/account_move_templates.xml",
        "reports/account_move_reports.xml",
    ],
    "installable": True,
    "application": False,
}
