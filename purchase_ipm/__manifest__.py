# -*- coding: utf-8 -*-
{
    'name': 'Purchase IPM',
    'summary': 'Purchase IPM',
    'description': 'Bloquea orden de compra en estados de aprobación y posteriores',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Purchase',
    'version': '19.0.0.0.1',
    "depends": [
        "purchase",
        "purchase_requisition",
        "project_purchase",
        "account_tax",
        "purchase_stock",
        "purchase_approval",
    ],
    "data": [
        "views/purchase_order_base.xml",
        "views/purchase_order_requisition.xml",
        "views/purchase_order_project.xml",
        "views/purchase_order_account_tax.xml",
        "views/purchase_order_stock.xml",
    ],
    "installable": True,
    "application": False,
}
