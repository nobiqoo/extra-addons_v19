{
    'name': 'Ventas Geoflora',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Confirmación masiva de cotizaciones, facturación consolidada por N° Invoice WebFlor '
               'e información WebFlor en facturas y cuentas por cobrar',
    'description': """
            Confirmación masiva de cotizaciones, facturación consolidada por N° Invoice WebFlor
            e información WebFlor en facturas y cuentas por cobrar
        """,
    'author': 'Odone-S.A.S',
    'website': 'https://www.odone.com.co',
    'license': 'LGPL-3',
    'depends': ['sale_baseline', 'webflor_sale_integration'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'wizard/sale_order_mass_confirm_views.xml',
        'wizard/sale_make_invoice_advance_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
