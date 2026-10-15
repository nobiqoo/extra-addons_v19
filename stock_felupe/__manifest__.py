# -*- coding: utf-8 -*-
{
    'name': 'Stock Felupe',
    'summary': 'Controles de margen y seguimiento de alistamiento y entregas',
    'description': """
        - Restringe ventas con un margen inferior al configurado por producto.
        - Lleva el estado de alistamiento de los traslados al pedido de venta.
        - Registra la empresa transportadora y su numero de guia en la entrega.
        - Calcula el reparto unitario de costos para subproductos de fabricacion.
    """,
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Sales',
    'version': '19.0.0.0.1',
    'depends': [
        'mrp',
        'sale',
        'sale_baseline',
        'sale_management',
        'sale_margin',
        'sale_purchase_baseline',
        'sale_stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/product_template_views.xml',
        'views/mrp_production_views.xml',
        'views/delivery_carrier_master_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/margin_warning_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
