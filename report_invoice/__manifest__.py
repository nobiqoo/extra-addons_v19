# -*- coding: utf-8 -*-
{
    'name': 'Invoice Report',
    'summary': '''
        View and create reports
    ''',
    'description': '''
        - report invoices.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'sales/sale',
    'license': 'LGPL-3',
    'version': '19.0.0.0.1',
    'depends': [
        'base_setup',
        'account_baseline',
        'account',
        'account_report',
    ],
    'data': [
        'security/ir.model.access.csv',
        'reports/report_invoice.xml',
        'views/menuitem_views.xml',
    ],
    'installable': True,
}
