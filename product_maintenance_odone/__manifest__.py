{
    'name': 'Product Maintenance Odone',
    'summary': 'Política de firmas y tipo de mantenimiento en órdenes de trabajo',
    'author': 'OdOne S.A.S',
    'website': 'https://www.odone.com.co/',
    'category': 'Repair',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'product_maintenance',
        'web',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/repair_order_views.xml',
        'reports/repair_order_report_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
