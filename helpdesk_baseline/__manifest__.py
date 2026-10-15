# -*- coding: utf-8 -*-
{
    'name': 'Helpdesk Baseline',
    'summary': '''
        - Income and expense tab.
    ''',
    'description': '''
        - Income and expense tab.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Services/Helpdesk',
    'version': '19.0.0.0.1',
    'depends': [
        'helpdesk',
        'helpdesk_timesheet',
        'sale',
        'purchase',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/helpdesk_ticket_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/res_config_settings_views.xml',
    ],
}
