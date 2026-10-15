{
    "name": "Purchase Request Custom",
    'version': '19.0.0.0.1',
    "depends": ["approvals", "purchase", "approvals_purchase"],
    'author': 'OdOne S.A.S.',
    "website": "http://www.odone.com.co",
    "category": "Purchases",
    "description": "Campos adicionales y lógica personalizada para requerimientos de compra.",
    "data": [
        "views/approval_request_view.xml",
        "views/purchase_order_view.xml",
        "reports/purchase_report_inherit.xml",
    ],
    "installable": True,
    "application": False,
    "license": "OPL-1",
}
