# -*- coding: utf-8 -*-
{
    'name': 'Inventario Art Home',
    'summary': '''
        Importación masiva de lotes y números de serie con cantidad desde Operaciones detalladas.
        Cantidad de cajas (manual), peso total, valor asegurable y cantidad de líneas en las transferencias y sus reportes.
        Total de cajas de las entregas en el pedido de venta.
        Pedido, vendedor, nota/instrucción de despacho y lotes en la remisión de entrega.
        La nota del pedido se copia a recolección, empaque y entrega y se imprime en sus reportes
    ''',
    'description': '''
        Mejora el asistente nativo "Importar lotes/series" de la ventana Operaciones detalladas.

        Remisión de entrega:

        - Cantidad de Cajas: entero mayor o igual a 0 que el usuario de bodega digita en las
          entregas y dropship del pedido. El pedido de venta muestra la suma de sus entregas y
          dropship no cancelados (formulario, lista, exportación y PDF del pedido).
        - Peso Total: peso del producto por la cantidad demandada (antes de validar)
          o hecha (después de validar). Los productos sin peso suman 0.
        - Valor Asegurable: porcentaje configurable (Ajustes de Inventario, por compañía)
          sobre el precio neto de la línea del pedido de venta por las cantidades de la
          transferencia. Editable por transferencia.
        - Cantidad de Líneas: lotes/series distintos por producto en las operaciones detalladas;
          un producto sin lote o sin reservar cuenta 1. Se recalcula al cambiar los lotes.
        - Los datos se ven en la pestaña "Información adicional", en la lista de
          transferencias (columnas opcionales y exportación) y en los reportes
          "Recibo de entrega", "Operaciones de recolección" y "Entradas y salidas".
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.1',
    'depends': [
        'stock',
        'base_import',
        'sale_stock',
        'stock_report',
        'point_of_sale',
        'pos_hr',
        'l10n_co_bloodo',
        'stock_lot_traceability_arthome',
        'purchase_import',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/stock_picking_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'report/report_deliveryslip.xml',
        'report/report_stockpicking_operations.xml',
        'report/report_inputs_and_outputs.xml',
        'report/report_picking_packages.xml',
        'report/report_return_slip.xml',
        'report/report_saleorder.xml',
        'report/report_invoice.xml',
        'wizard/stock_picking_lot_import_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stock_arthome/static/src/widgets/generate_dialog_patch.js',
            'stock_arthome/static/src/widgets/generate_dialog_patch.xml',
        ],
    },
}
