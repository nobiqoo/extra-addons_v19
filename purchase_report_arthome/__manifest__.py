# -*- coding: utf-8 -*-
{
    'name': 'Ajustes de Reportes de Compra e Inventario',
    'summary': '''
        Separa la referencia interna en los PDF de compra y muestra el Documento Origen en los PDF de transferencias
    ''',
    'description': '''
        Ajusta el formato PDF de la Orden de Compra y de la Solicitud de Cotización:

        - Nueva columna "Referencia Interna" entre Descripción y Cantidad.
        - La descripción de la línea se muestra sin el código de referencia.
        - La Orden de Compra (PDF y portal del proveedor) no muestra la columna
          Impuestos en las líneas; los impuestos se discriminan en los totales.

        Ajusta los formatos PDF de las transferencias (Operaciones de recolección,
        Recibo de entrega, Recibo de devolución, Paquetes, Reporte de recepción y
        etiqueta de recepción):

        - Etiqueta "Documento Origen:" con el valor del campo origen de la transferencia.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Inventory/Purchase',
    'version': '19.0.1.0.0',
    'depends': ['purchase', 'stock'],
    'data': [
        'reports/purchase_order_report_templates.xml',
        'reports/purchase_quotation_report_templates.xml',
        'reports/stock_picking_report_templates.xml',
        'views/purchase_portal_templates.xml',
    ],
}
