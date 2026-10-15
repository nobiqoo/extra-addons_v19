# -*- coding: utf-8 -*-
{
    'name': 'Purchase Approval',
    'summary': '''
        - Aprobación de Compras
    ''',
    'description': '''
        - Aprobación de Compras
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Services/Project',
    'version': '19.0.0.0.1',
    'depends': [
        'purchase',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/purchase_approval_setting_views.xml',
        'views/purchase_order_views.xml',
        'wizard/purchase_approval_budget_wizard_views.xml',
    ],
}
