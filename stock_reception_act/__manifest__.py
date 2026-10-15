# -*- coding: utf-8 -*-
{
    'name': 'Stock Reception Act',
    'summary': '''
        - Acta de Recepción, Inventario o Devolución de Dispositivos Médicos e Insumos.
    ''',
    'description': '''
        - Campos regulatorios en las recepciones de inventario (marca, presentación
          comercial, registro sanitario, vida útil, clase de riesgo) y reporte PDF
          "Acta de Recepción" para la línea de salud y movilidad.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.1',
    'depends': [
        'stock',
        'product_expiry',
        'product_brand',
    ],
    'data': [
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/stock_picking_views.xml',
        'report/stock_picking_reception_act.xml',
        'report/stock_picking_reception_act_templates.xml',
    ],
}
