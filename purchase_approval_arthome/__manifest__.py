# -*- coding: utf-8 -*-
{
    'name': 'Aprobación de Compras Art Home',
    'summary': '''
        Ventana de alternativas de cotización al confirmar automáticamente una orden de compra aprobada
    ''',
    'description': '''
        - Muestra la ventana nativa de alternativas al aprobar una orden con confirmación automática
        - Cancela alternativas en aprobación o aprobadas y las retira de la bandeja de los aprobadores
        - Notifica al comprador cuando la decisión sobre las alternativas queda pendiente
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Inventory/Purchase',
    'version': '19.0.0.0.1',
    'depends': [
        'purchase_approval',
        'purchase_requisition',
    ],
    'data': [
        'data/mail_activity_type_data.xml',
        'views/purchase_approval_setting_views.xml',
    ],
}
