# -*- coding: utf-8 -*-
{
    'name': 'Stock Baseline',
    'summary': '''
        - Llevar notas de los pedidos de venta a las ordenes de entrega (política).
    ''',
    'description': '''
        - Llevar notas de los pedidos de venta a las ordenes de entrega (política).
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.1',
    'depends': [
        'sale_stock',
        'stock_account'
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'security/stock_baseline_security.xml',
        'views/res_config_settings_views.xml',
        'views/stock_picking_views.xml',
        'views/product_template_views.xml',
        'views/stock_picking_type_views.xml',
        'views/stock_warehouse_views.xml',
    ],
}
