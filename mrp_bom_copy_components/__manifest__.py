# -*- coding: utf-8 -*-
{
    'name': "Copy BoM Components",
    'summary': "Copy existing components from other Bills of Materials",
    'description': """
Adds a button in the Components tab of the Bill of Materials to select
component lines from other Bills of Materials and copy them.""",
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Manufacturing/Manufacturing',
    'version': '19.0.1.0.0',
    'depends': [
        'mrp',
    ],
    'data': [
        'views/mrp_bom_views.xml',
    ],
    'license': 'LGPL-3',
}
