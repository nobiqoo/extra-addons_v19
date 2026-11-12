# -*- coding: utf-8 -*-
{
    'name': 'Transportadora y Guía en Pedidos de Venta',
    'summary': '''
        Transportadora y número de guía en el pedido de venta, con propagación a entregas y actualización masiva.
        Reporte de información de guías para exportar cliente, dirección de envío, factura y valor asegurable.
        Cotización y pedido de venta sin columna Impuestos en las líneas (PDF y portal)
        Nombre y correo del vendedor en el pie de página del PDF de cotización y pedido de venta
    ''',
    'description': '''
        Permite registrar la transportadora y el número de guía directamente
        en el Pedido de Venta:

        - Marca "Es Transportista" en el contacto (pestaña Ventas y Compras).
        - Campos Transportadora y Número de Guía en la pestaña "Otra Información"
          del pedido, editables en cualquier estado, y visibles en las listas de
          cotizaciones y pedidos, con búsqueda por ambos.
        - check "Propagar a Entregas": copia ambos datos a las entregas del
          pedido al confirmarlo y cada vez que cambian.
        - Asistente de actualización masiva desde las listas de cotizaciones y
          pedidos: carga un archivo CSV o XLSX y actualiza los pedidos usando el
          número del pedido como clave. La transportadora se identifica por NIT
          y, si hay conflicto, por nombre.

        Formato de Cotización / Pedido de venta (PDF, PRO-FORMA y portal del cliente):

        - Las líneas no muestran la columna Impuestos; los impuestos se siguen
          calculando y se discriminan en el bloque de totales.
        - El pie de página del PDF incluye "Asesor comercial: nombre · correo" del
          vendedor de la orden, debajo de los datos de la compañía, en todos los
          diseños de documento. No se imprime si la orden no tiene vendedor o
          este no tiene correo; los demás documentos conservan su pie.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'depends': ['sale_stock', 'stock_arthome'],
    'data': [
        'security/ir.model.access.csv',
        'security/sale_arthome_security.xml',
        'data/ir_exports_data.xml',
        'wizard/sale_carrier_update_wizard_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'report/sale_shipping_report_views.xml',
        'report/sale_order_report_templates.xml',
        'report/report_layout_templates.xml',
        'views/sale_portal_templates.xml',
    ],
}
