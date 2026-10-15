# -*- coding: utf-8 -*-
{
    'name': 'Purchase Service Acceptance',
    'summary': '''
        - Service Acceptance for purchase orders
    ''',
    'description': '''
        Replicates, for Service products, the same principle Odoo uses natively
        for stockable products (receipt confirmed before the vendor bill arrives):
        an acceptance document per purchase order, with ordered/accepted/pending
        quantity control, that feeds the native qty_received field on the
        purchase order line.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Inventory/Purchase',
    'version': '19.0.0.1.0',
    'depends': [
        'purchase',
        'account',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/purchase_service_acceptance_views.xml',
        'views/purchase_order_views.xml',
        'views/account_move_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'purchase_service_acceptance/static/src/js/*.js',
            'purchase_service_acceptance/static/src/scss/*.scss',
            'purchase_service_acceptance/static/src/xml/*.xml',
        ],
    },
    'application': True,
    'installable': True,
}
