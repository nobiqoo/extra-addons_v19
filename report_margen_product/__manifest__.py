# -*- coding: utf-8 -*-
{
    'name': 'Report Margen',
    'summary': '''
        View and create reports
    ''',
    'description': '''
        - report Margen de productos.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'sales/sale',
    'license': 'LGPL-3',
    'version': '19.0.0.0.1',
    'depends': [
        'product_brand',
        'stock',
        'sale'
    ],
    'data': [
        'security/ir.model.access.csv',
        'reports/report_margen.xml',
        'views/menuitem_views.xml',
    ],
    'installable': True,
}
