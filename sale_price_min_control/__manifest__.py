# -*- coding: utf-8 -*-
{
    'name': 'Control de Descuentos por Monto Mínimo',
    'summary': """
        Bloquea la confirmación de cotizaciones con precios por debajo del
        mínimo de la lista de precios, con aprobación de excepción por el
        Responsable Comercial.
    """,
    'description': """
        - Agrega el campo Precio Mínimo en las reglas de las listas de
          precios.
        - Al confirmar una cotización, valida el precio neto (con descuento)
          de cada línea contra el precio mínimo de la regla de lista aplicada;
          las reglas sin precio mínimo no se controlan.
        - Si alguna línea está por debajo de ese mínimo, bloquea la
          confirmación con un mensaje de advertencia.
        - Un grupo dedicado (Responsable Comercial) puede aprobar la
          excepción para permitir la confirmación; queda registrado en el
          Chatter de la orden.
    """,
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'depends': ['sale', 'sale_management'],
    'data': [
        'security/security.xml',
        'views/product_pricelist_views.xml',
        'views/sale_order_views.xml',
    ],
}
