# -*- coding: utf-8 -*-
{
    'name': 'Account IPM',
    'summary': 'Ajustes de Contabilidad exclusivos de IPM',
    'description': 'Personalizaciones contables que solo aplican a IPM',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Accounting',
    'version': '19.0.0.0.1',
    'depends': [
        'account',
        'l10n_co_data_bloodo',
        'l10n_co_reports',
    ],
    'data': [
        'views/account_tax_views.xml',
    ],
    'installable': True,
    'application': False,
}
