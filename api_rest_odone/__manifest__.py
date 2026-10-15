# -*- coding: utf-8 -*-
{
    'name': 'API REST OdOne - Asientos Contables',
    'summary': 'Endpoint REST para la creación de asientos contables mediante integración externa.',
    'description': '''
        Módulo que expone un endpoint REST para crear movimientos contables (asientos)
        desde sistemas externos. Soporta:

        - Creación de uno o más asientos contables en una sola petición.
        - Validación de cuenta contable, tercero (NIT/VAT) y centro de costo.
        - Publicación automática del asiento si se indica en el payload.
        - Autenticación mediante Bearer Token (API Key de Odoo).
        - Configuración del diario de integración por compañía.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Accounting/Accounting',
    'license': 'OPL-1',
    'version': '19.0.0.1',
    'depends': [
        'account',
        'analytic',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
