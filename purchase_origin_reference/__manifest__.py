{
    'name': 'Purchase Order - Documento Origen',
    'version': '19.0.0.0.1',
    'license': 'LGPL-3',
    'category': 'Purchases',
    'summary': 'Añade un campo para enlazar documentos origen en órdenes de compra.',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'contributors': [
        'Andres Gil andresgil@odone.com.co'
    ],
    'depends': ['purchase'],
    'data': [
        'views/purchase_order_view.xml',
    ],
    'installable': True,
    'application': False,
}
