# -*- coding: utf-8 -*-
{
    'name': 'Custom Sale My Home',
    'summary': '''
        - Compras relacionadas en lista de ventas + Número de Guía de entrega personalizada
    ''',
    'description': '''
        - Compras relacionadas en lista de ventas +  Número de Guía de entrega personalizada
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Inventory/Inventory',
    'version': '19.0.1.0.0',
    'depends': [
        'sale',
        'purchase',
        'sale_stock', 
        'purchase_stock',
        'sale_purchase'
    ],
    'data': [
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
