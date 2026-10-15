# -*- coding: utf-8 -*-
{
    'name': "Stock Adjustments",

    'summary': "Ajustes adicionales para el módulo de inventario",

    'description': """
        - Grupo para ajustes de inventario
        - Restricción al menú de Inventario físico
        - Restricción al aplicar automáticamente en reabastecimiento
    """,

    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co',

    'category': 'Stock',
    'version': '19.0.0.0.1',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['product','stock'],

    # always loaded
    'data': [
        'security/stock_adjustments_security.xml',
        'views/stock_quant_views.xml',
    ],
}

