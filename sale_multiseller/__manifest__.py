# -*- coding: utf-8 -*-
{
    'name': 'Multivendedor por Cliente',
    'summary': '''
        Varios vendedores asignados por contacto y visibilidad restringida de contactos, pedidos e informes de venta.
    ''',
    'description': '''
        - Campo "Vendedores asignados" en el contacto: un cliente puede tener varios vendedores a la vez.
        - El Comercial del contacto (vendedor principal) solo se elige entre sus vendedores asignados
          y se propaga al pedido como Vendedor.
        - En cotizaciones y pedidos, el Vendedor solo ofrece los vendedores asignados al cliente
          (todos los vendedores si el cliente no tiene vendedores asignados).
        - Grupo "Vendedor restringido" en Ventas: solo ve, busca y selecciona sus contactos asignados
          (más sus direcciones, los contactos sin vendedor asignado, los usuarios internos y la compañía),
          y solo edita sus contactos asignados. Hereda "Usuario: solo documentos propios", por lo que
          solo ve sus pedidos y sus datos en los informes de ventas.
        - Al crear un contacto, el vendedor restringido queda asignado automáticamente.
        - Compatible con el Punto de Venta: la regla se resuelve con el índice de la tabla de vendedores.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'depends': ['sale'],
    'data': [
        'security/sale_multiseller_security.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
    ],
}
