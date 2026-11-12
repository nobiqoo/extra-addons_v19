# -*- coding: utf-8 -*-
{
    'name': 'Purchase Brillaseo',
    'summary': '''
        Agrega campos para Brillaseo
    ''',
    'description': '''
        - Agrega el campo Ciudad en cada línea de Orden de Compra.
        - Hereda la Ciudad de la línea de Orden de Compra a la línea de la Factura de Proveedor.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Purchases',
    'version': '19.0.1.0.0',
    'depends': [
        'purchase',
        'account_tax',
    ],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
}
