# -*- coding: utf-8 -*-
{
    'name': 'Approval RFQ ISO',
    'summary': 'Cotizaciones de compra independientes por aprobacion',
    'description': 'Evita mezclar RFQ entre aprobaciones y vincula la compra con su aprobacion origen.',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Purchases',
    'version': '19.0.1.0',
    'depends': [
        'approval_request_custom',
    ],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
