# -*- coding: utf-8 -*-
{
    'name': 'Purchase Import',
    'summary': '''
        Purchase imports
    ''',
    'description': '''
        - falta descripcion.
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': [
        'Juan Arcos juanparmer@gmail.com'
    ],
    'website': 'https://www.odone.com.co/',
    'category': 'Inventory/Purchase',
    'license': 'LGPL-3',
    'version': '19.0.0.0.1',
    'depends': [
        'product_brand',
        'purchase_stock',
        'stock_landed_costs',
        'report_xlsx',
    ],
    'data': [
        'security/res_groups_security.xml',
        'security/ir_rule_security.xml',
        'security/ir.model.access.csv',
        'data/account_incoterms_data.xml',
        'data/ir_sequence_data.xml',
        'data/ir_ui_menu_data.xml',
        'data/res_partner_data.xml',
        'data/stock_picking_data.xml',
        'views/account_incoterms_view.xml',
        'views/account_move_view.xml',
        'views/product_template_view.xml',
        'views/purchase_import_view.xml',
        'views/purchase_order_view.xml',
        'views/res_config_settings_views.xml',
        'views/stock_landed_view.xml',
        'views/stock_move_line_view.xml',
        'views/stock_picking_view.xml',
        'views/stock_move_dim_view.xml',
        'views/purchase_order_report_views.xml',
        'views/purchase_order_simple_report_views.xml',
        'reports/purchase_import_report.xml',
        'views/import_dim_wizard_views.xml',
    ],
}
