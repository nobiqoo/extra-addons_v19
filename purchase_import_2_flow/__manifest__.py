# -*- coding: utf-8 -*-
{
    'name': 'Purchase Import - Flujo de Validación PR',
    'summary': '''
        Restaura el flujo de validación de importaciones previo (estilo PR)
    ''',
    'description': '''
        Sobrescribe purchase.import.action_validate() y stock.picking.button_validate()
        para permitir validar el picking de recepción desde Inventario/Compras
        (en vez de bloquear y exigir hacerlo desde el registro de importación),
        cerrando la importación automáticamente cuando ya no queden pickings pendientes.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Inventory/Purchase',
    'license': 'LGPL-3',
    'version': '19.0.0.0.1',
    'depends': [
        'purchase_import',
    ],
    'data': [],
}
