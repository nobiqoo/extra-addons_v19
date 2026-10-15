# -*- coding: utf-8 -*-
{
    'name': 'Account Voucher Check',
    'summary': '''
        Modulo cheques en voucher
    ''',
    'description': '''
        Modulo cheques en voucher
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': [
        'Jorge Cerquera jorgec@odone.com.co'
    ],
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.0.0.1',
    'depends': [
        'account',
        'contacts',
        'account_voucher'
    ],
    'data': [
        'views/account_voucher_views.xml',
        'report/account_voucher_templates.xml',
        'report/account_voucher_reports.xml',
    ],
    'installable': True,
}
