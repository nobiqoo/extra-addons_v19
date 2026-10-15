# -*- coding: utf-8 -*-
{
    'name': 'Contabilidad - Colombo Americano',
    'summary': '''
        ReteICA por sede de operación en facturación y punto de venta
    ''',
    'description': '''
        Automatiza la aplicación del impuesto de Industria y Comercio Retenido
        (ReteICA) según la sede en la que se origina el documento (tarea 10340):

        - Maestro "Sedes de Operación" en Contabilidad, administrado por el
          equipo contable: nombre, ciudad y el ReteICA de venta y de compra que
          corresponde al municipio.
        - Campo "Sede de Operación" en la cabecera de las facturas y notas de
          crédito de cliente y de proveedor. Al seleccionarlo, el sistema
          inyecta en todas las líneas de producto el ReteICA que corresponde
          según el tipo de documento, sin tocar el IVA ni los demás impuestos
          del producto. Las líneas que se agreguen después también lo reciben,
          y al cambiar o vaciar la sede el impuesto anterior se reemplaza.
        - Sede de operación por punto de venta: las líneas del POS nacen con el
          ReteICA de la sede, tanto en el ticket como en el asiento contable.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Accounting/Accounting',
    'license': 'OPL-1',
    'version': '19.0.0.1',
    'depends': [
        'account',
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_operation_site_views.xml',
        'views/account_move_views.xml',
        'views/pos_config_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'account_colombo/static/src/js/pos_operation_site.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
