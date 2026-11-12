# -*- coding: utf-8 -*-
{
    'name': 'Creación Automática de Lotes por Cuenta Analítica',
    'summary': '''
        - Creación automática de lotes de inventario a partir de la cuenta analítica de la Orden de Compra
    ''',
    'description': '''
        - Al confirmar una Orden de Compra con cuenta analítica del plan configurado en la compañía, hereda el
          nombre de la cuenta analítica como número de lote/serie de cada producto en la recepción.
        - Evita la creación manual de lotes para este proceso y controla duplicados y lotes archivados.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Inventory/Purchase',
    'version': '19.0.0.0.1',
    'depends': [
        'purchase_stock',
        'analytic',
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
