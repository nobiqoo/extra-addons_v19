{
    'name': 'WebFlor Sale Integration',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Campos comerciales, de líneas y logísticos para trazabilidad con WebFlor',
    'description': """""",
    'author': 'Odone-S.A.S',
    'website': 'https://www.odone.com.co',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'l10n_co'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'post_init_hook': '_post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
