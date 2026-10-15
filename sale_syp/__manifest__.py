# -*- coding: utf-8 -*-
{
    'name': "Sale SYP",

    'summary': """
        Custom Module for noveltys in SYP""",

    'description': """
        Custom Module for noveltys in SYP
    """,

    'author': "OdOne S.A.S",
    'website': "https://www.odone.com.co",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Product',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['product', 'sale_margin'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/sale_order_views.xml',
    ],
}
