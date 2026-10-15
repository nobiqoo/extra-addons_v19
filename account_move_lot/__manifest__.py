# -*- coding: utf-8 -*-
{
    'name': 'Account Move Lot',
    'summary': '''
        Account Move Lot
    ''',
    'description': '''
        - Lote en líneas de factura
    ''',
    'author': 'OdOne S.A.S',
    'contributors': [
        'Jorge Cerquera jorgec@odone.com.co',
    ],
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.0.0.1',
    'depends': [
        'l10n_co_bloodo',
        'sale_stock',
    ],
    'data': [
        'views/account_move_views.xml',
        'reports/account_invoice.xml',
    ],
}
