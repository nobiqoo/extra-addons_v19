# -*- coding: utf-8 -*-
{
    'name': 'Website Baseline',
    'summary': '''
        Portal de proveedores: certificados de retenciones, estado de cuenta y pagos
    ''',
    'description': '''
        Funciones del portal de la localización colombiana:
        - Solicitud y descarga de certificados de retenciones por el proveedor.
        - Estado de cuenta en PDF desde las facturas de proveedor del portal.
        - Fecha y valor del último pago en la lista de facturas del portal.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Website',
    'license': 'LGPL-3',
    'version': '19.0.0.0.0',
    'depends': [
        'website',
        'portal',
        'account',
        'tax_certificate_management',
    ],
    'data': [
        'views/portal_certificates_templates.xml',
        'views/portal_invoices_templates.xml',
        'report/vendor_statement_report.xml',
    ],
    'installable': True,
    'application': False,
}
