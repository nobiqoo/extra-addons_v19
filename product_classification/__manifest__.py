# -*- coding: utf-8 -*-
{
    'name': 'Product Clasification',
    'summary': 'Product Clasification',
    'description': 'Product Clasification',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.1',
    'depends': [
        'stock',
        'product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_classification_views.xml',
        'views/product_product_views.xml',
        'views/stock_quant_views.xml',
    ],
}
