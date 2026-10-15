# -*- coding: utf-8 -*-
{
    'name': "Inventory information report distritodo",

    'summary': "This module generates an inventory turnover analysis.",

    'description': """
This module generates an inventory turnover analysis by retrieving, per product, the on-hand quantity by warehouse, units sold to date, and the date of the last product receipt.
    """,

    'author': 'ODONE SAS',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.1.0',
    'license': 'LGPL-3',

    'depends': ['stock'],

    'data': [
        'security/ir.model.access.csv',
        'views/inventory_turnover_analysis_views.xml',
        'wizard/inventory_turnover_analysis_wizard.xml'
    ],

}

