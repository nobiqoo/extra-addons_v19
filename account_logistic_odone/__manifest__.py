# -*- coding: utf-8 -*-
{
    'name': 'Invoicing Losgistic',
    'summary': '''
        Invoices & Payments
    ''',
    'description': '''
        Invoicing & Payments
    ''',
    'author': 'OdOne S.A.S',
    'contributors': ['Juan Arcos juanparmer@gmail.com'],
    'website': 'https://www.odone.com.co/',
    'category': 'Accounting/Accounting',
    'license': 'LGPL-3',
    'version': '19.0.1.0.0',
    'depends': [
        'account_baseline',
        'analytic',
        'contacts',
        'date_range',
        'report_xlsx'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_account_views.xml',
        'report/account_analytic_report.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'wizard/account_analytic_wizard_view.xml',
    ],
}
