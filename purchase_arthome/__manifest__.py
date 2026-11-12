# -*- coding: utf-8 -*-
{
    'name': 'Compras Art Home',
    'summary': '''
        Tipo de Compra (Nacional, Importación, Triangulación) en las órdenes de compra y en el Análisis de Compras
    ''',
    'description': '''
        Clasifica automáticamente cada orden de compra según su naturaleza
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Inventory/Purchase',
    'version': '19.0.0.0.1',
    'depends': [
        'purchase_stock',
        'stock_dropshipping',
        'purchase_import',
    ],
    'data': [
        'views/purchase_order_views.xml',
        'report/purchase_report_views.xml',
    ],
}
