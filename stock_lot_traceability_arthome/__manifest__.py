# -*- coding: utf-8 -*-
{
    'name': 'Comentario de Trazabilidad en Lotes',
    'summary': '''
        Comentario/observacion permanente y numero de importacion en lotes y numeros de serie
    ''',
    'description': '''
        Reutiliza el campo nativo note de stock.lot como comentario de trazabilidad
        y lo muestra en la lista de lotes, en la seleccion de lote de Punto de Venta,
        en los movimientos de inventario y en el Informe de Trazabilidad.

        Registra automaticamente en el lote/serie el numero de la importacion
        (Compra > Importaciones) por la que fue recibido y lo muestra, sin permitir
        su edicion, en lotes, existencias y movimientos de inventario.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.1',
    'depends': [
        'stock',
        'point_of_sale',
        'purchase_import',
    ],
    'data': [
        'views/stock_lot_views.xml',
        'views/stock_move_line_views.xml',
        'views/stock_quant_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stock_lot_traceability_arthome/static/src/client_actions/stock_traceability_report_backend.xml',
        ],
        'point_of_sale._assets_pos': [
            'stock_lot_traceability_arthome/static/src/app/components/popups/select_lot_popup/select_lot_popup.js',
            'stock_lot_traceability_arthome/static/src/app/components/popups/select_lot_popup/select_lot_popup.xml',
        ],
    },
}
