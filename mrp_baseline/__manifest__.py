# -*- coding: utf-8 -*-
{
    'name': "Manufacturing User",
    'summary': "Manufacturing Orders & BOMs",
    'description': "Manufacturing Orders & BOMs",
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Manufacturing/Manufacturing',
    'version': '19.0.0.0.1',
    'depends': [
        'mrp_landed_costs'
    ],
    'data': [
        'security/res_groups_security.xml',
        'security/ir.model.access.csv',
        'data/account_journal_data.xml',
        'data/product_product_data.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/stock_landed_views.xml',
        'views/mrp_routing_views.xml',
        'wizard/production_account_close_views.xml',
    ],
    'demo': [
        'demo/product_product_demo.xml',
    ],
    'license': 'LGPL-3',
}
