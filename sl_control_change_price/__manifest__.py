# -*- coding: utf-8 -*-
{
    'name': "Sale Control Change Price",
    'summary': """This module is used to have control over the price change in the sales order.""",
    'description': """This module is used to have control over the price change in the sales order.""",
    'author': "Wohoo",
    'website': "http://www.wohoo.tech",
    'category': 'Uncategorized',
    'version': '16.1',
    'depends': ['sale', 'sale_management','product'],
    'data': [
        'security/groups.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],

}
