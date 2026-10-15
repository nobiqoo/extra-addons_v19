# -*- coding: utf-8 -*-
{
    'name': 'Accounting Anker',
    'summary': '''
        Ajustes de contabilidad exclusivos de Anker
    ''',
    'description': '''
        - Restaura los filtros rápidos "Pagado" y "Revertido" en la
          búsqueda de Facturas de clientes, presentes en v17 y no
          incluidos en la vista base de facturas de esta instancia v19.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Accounting/Accounting',
    'license': 'LGPL-3',
    'version': '19.0.1.0.0',
    'depends': [
        'account',
        'account_reports',
    ],
    'data': [
        'views/account_move_views.xml',
        'views/followup_report_views.xml',
    ],
}
