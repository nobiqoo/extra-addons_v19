# -*- coding: utf-8 -*-
{
    'name': 'Compras - Colombo Americano',
    'summary': '''
        Bloques de contacto (Vendedor / Contacto) en el reporte de orden de compra
    ''',
    'description': '''
        Agrega al formato impreso de la orden de compra dos bloques de contacto:

        - Vendedor: persona de contacto del lado del proveedor, seleccionable
          manualmente en la orden de compra.
        - Contacto: persona de Colombo responsable de la orden (Comprador),
          con su cargo, teléfono y correo.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Purchases',
    'license': 'OPL-1',
    'version': '19.0.0.1',
    'depends': [
        'purchase',
        'purchase_stock',
    ],
    'data': [
        'views/purchase_order_views.xml',
        'reports/purchase_order_report_templates.xml',
        'reports/purchase_quotation_report_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
