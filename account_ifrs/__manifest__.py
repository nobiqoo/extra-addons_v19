# -*- coding: utf-8 -*-
{
    'name': 'IFRS Account',
    'summary': '''
        IFRS Account
    ''',
    'description': '''
        IFRS Account
        - falta descripcion.
    ''',
    'author': 'OdOne S.A.S',
    'contributors': [
        'Juan Arcos juanparmer@gmail.com'
    ],
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.0.1',
    'depends': [
        'account'
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'security/res_groups_security.xml',
        'views/account_account_view.xml',
        'views/account_move_view.xml',
    ],
}
