# -*- coding: utf-8 -*-
{
    'name': "Profitability Report ",

    'summary': "Reporte de Rentabilidad por Producto",

    'description': """
        Generación de Reporte de Rentabilidad por Producto
    """,

    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Reports',
    'version': '19.0.0.0.1',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['account', 'stock', 'sale', 'account_baseline'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/profitability_report_security.xml',
        'data/server_actions.xml',
        'views/sale_picking_invoice_mapping_views.xml',
        'views/profitability_report_views.xml',
        'data/ir_cron.xml',
        'wizard/profitability_report_wizard_views.xml',
    ],
}
