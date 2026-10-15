# -*- coding: utf-8 -*-
{
    'name': 'Invoicing Baseline',
    'summary': '''
        Invoices & Payments
    ''',
    'description': '''
        - Administrar terceros en lineas de factura de venta (Política).
        - Administrar terceros en lineas de factura de proveedor (Política).
        - Bloquear fechas cuando hay asientos en borrador (Política).
        - Cuenta de devoluciones en el producto.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Accounting/Accounting',
    'license': 'OPL-1',
    'version': '19.0.0.1',
    'depends': [
        'account',
        'account_accountant',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/product_category_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'reports/account_details_report.xml',
        'reports/report_account_details.xml',
        'reports/account_invoice_report_views.xml',
        'wizard/account_details_views.xml',
        'wizard/accounting_account_closing_views.xml'
    ],
}
