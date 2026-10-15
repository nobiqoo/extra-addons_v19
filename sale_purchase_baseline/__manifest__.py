# -*- coding: utf-8 -*-
{
    'name': "Sale Purchase Order",

    'summary': "Show products in sales orders",

    'description': "Show products in sales orders",

    'author': "Odone",
    'website': "https://www.odone.com.co",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sales',
    'version': '19.0.0.0.1',

    # any module necessary for this one to work correctly
    'depends': ['sale', 'product', 'purchase'],

    # always loaded
    'data': [
        "views/res_config_view.xml",
    ],

    # license
    'license': 'LGPL-3',
}
