# -*- coding: utf-8 -*-
{
    'name': 'Estado de Cumplimiento de Despacho en Pedidos de Venta',
    'summary': '''
        Estado de cumplimiento de entrega (exacto, parcial, faltante o excedente) en pedido de venta
    ''',
    'description': '''
        Agrega el campo "Estado de Cumplimiento de Entrega" en form del
        Pedido de Venta, calculado automaticamente al validar las entregas:

        - Pendiente: confirmado sin ninguna entrega despachada todavia.
        - Parcial: hay entrega parcial con una Orden de Entrega aun abierta
          (backorder pendiente).
        - Entregado Total: la cantidad despachada coincide con la solicitada.
        - Entregado de Menos (Faltante): se cerro la entrega sin backorder y
          quedo por debajo de lo solicitado.
        - Entregado de Mas (Excedente): se despacho mas de lo solicitado.

        Solo se consideran las lineas con entrega fisica (metodo de calculo
        "Movimientos de Stock"); las lineas de servicio no participan en el
        calculo agregado.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'depends': ['sale_stock'],
    'data': [
        'views/sale_order_views.xml',
    ],
}
