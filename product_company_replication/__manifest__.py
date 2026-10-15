# -*- coding: utf-8 -*-
{
    'name': 'Product Company Replication',
    'summary': '''
        - Replicar y sincronizar el maestro de productos entre las compañías del grupo.
    ''',
    'description': '''
        - Botón "Replicar producto" que crea el mismo producto en las compañías seleccionadas.
        - Apuntadores de trazabilidad: producto origen y productos replicados.
        - Al guardar cambios en los campos maestros, se propone sincronizarlos en las
          compañías vinculadas mediante un asistente de confirmación.
        - Avisa cuando alguna réplica está archivada y reporta los errores por compañía
          sin abortar el resto de la sincronización.
        - No se tocan datos que varían por compañía: costos, precios, impuestos,
          cuentas contables, rutas, proveedores ni existencias.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.1',
    'depends': [
        'product',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/product_replicate_wizard_views.xml',
        'wizard/product_sync_wizard_views.xml',
        'views/product_template_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'product_company_replication/static/src/js/product_replication_form.js',
            'product_company_replication/static/src/css/product_replicate_wizard.css',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
