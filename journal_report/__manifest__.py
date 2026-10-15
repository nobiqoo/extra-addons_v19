# -*- coding: utf-8 -*-
{
    'name': 'Report journal',
    'summary': '''
        Auditoria de Diarios
    ''',
    'description': '''
        -
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co',
    'category': 'account/accountant',
    'license': 'LGPL-3',
    'version': '19.0.0.0.1',
    'depends': [
        'base_setup',
        'account',
        'account_report',
    ],
    'data': [
         'security/ir.model.access.csv',
         'reports/report_journal.xml',
         'views/menuitems.xml',
    ],
}
