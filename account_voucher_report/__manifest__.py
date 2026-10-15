# -*- coding: utf-8 -*-
{
    'name': 'Voucher Account Report',
    'summary': '''
        Reporte de pagos
    ''',
    'description': '''
        - Reporte de pagos
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.0.0.1',
    'depends': [
        'account_voucher'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/account_voucher_report_security.xml',
        'views/account_voucher_report_views.xml',
    ],
}
