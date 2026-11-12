{
    'name': 'Stock Metromat',
    'summary': 'Formatos de ingreso y remisión de equipos en órdenes de trabajo',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Inventory/Inventory',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'product_maintenance_odone',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'data/repair_service_type_data.xml',
        'views/repair_service_type_views.xml',
        'views/repair_order_views.xml',
        'reports/repair_order_format_templates.xml',
        'reports/repair_order_format_reports.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
