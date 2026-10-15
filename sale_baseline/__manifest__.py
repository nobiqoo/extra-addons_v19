# -*- coding: utf-8 -*-
{
    'name': 'Sale Baseline',
    'summary': '''
        Sale Baseline
    ''',
    'description': '''
        - Restringir la edición del campo de vendedor en ventas y facturas (Política).
        - Permite agregar una etiqueta y bloquear al cliente que no ha comprado en los últimos meses (Política).
        - No permite confirmar el pedido de venta si no hay cantidades disponibles.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Sales',
    'version': '19.0.0.0.1',
    'depends': ['account_voucher', 'sale_stock', 'sale_management', 'sale_purchase_baseline', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'security/sale_baseline_groups.xml',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/product_product_views.xml',
        'views/product_category_views.xml',
        'views/res_partner_views.xml',
        'views/profitability_report_views.xml',
        'views/stock_picking_views.xml',
        'wizard/profitability_report_wizard_views.xml'
    ],
}
