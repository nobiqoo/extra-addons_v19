# -*- coding: utf-8 -*-
{
    'name': "Negative Inventories",

    'summary': """
        Negative inventory management module in Odoo""",

    'description': """
        Negative inventory management module in Odoo
    """,

    'author': 'OdOne S.A.S.',
    'website': "https://www.odone.com.co/",
    'license': 'OPL-1',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Inventory',
    'version': '19.0.0.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
    ],
}
