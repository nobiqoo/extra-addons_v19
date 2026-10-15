# -*- coding: utf-8 -*-
{
    'name': 'E-Invoicing to RNDC',
    'summary': '''
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com
    ''',
    'description': '''
        Long description of module's purpose
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': ['Bernardo David Lara Guevara <blara@odone.com.co, bloodo.dev.solutions@gmail.com>'],
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Accounting/Localizations/EDI',
    'version': '19.0.0.0.1',
    'depends': [
        'l10n_co_bloodo'
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'views/res_users_views.xml',
        'views/request_templates.xml',
    ],
}
