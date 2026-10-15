# -*- coding: utf-8 -*-
{
    'name': 'Sale Work',
    'summary': '''
        - Ventas Obras
    ''',
    'description': '''
        - Ventas Obras
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.1',
    'depends': [
        'sale',
        'account_reports'
    ],
    'data': [
        'data/aged_partner_balance_works.xml',
        'data/account_report_actions.xml',
        'data/menuitems.xml',
        'security/ir.model.access.csv',
        'views/sale_order_work_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
    ],
   'assets': {
    'web.assets_backend': [
        'sale_order_work/static/src/**/*.xml',
        'sale_order_work/static/src/**/*.js',
    ],
}
}
