# -*- coding: utf-8 -*-
{
    'name': 'IFRS Assets Management',
    'summary': '''
        IFRS Assets Management
    ''',
    'description': '''
        - IFRS Assets Management
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'contributors': [
        'Juan Arcos juanparmer@gmail.com'
    ],
    'category': 'Accounting/Accounting',
    'license': 'LGPL-3',
    'version': '19.0.0.1',
    'depends': [
        'account_asset',
        'account_ifrs',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_asset_view.xml',
        'views/asset_location_views.xml',
        'wizard/report_asset_wizard_views.xml'
    ],
}
