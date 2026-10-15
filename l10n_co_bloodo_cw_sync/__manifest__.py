# -*- coding: utf-8 -*-
{
    'name': 'l10n_co_bloodo_cw_sync',
    'summary': '''
        Extención FE OdOne
    ''',
    'description': '''
        - Formato PDF factura.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'http://www.odone.com.co',
    'category': 'Accounting/Localizations/EDI',
    'license': 'OPL-1',
    'version': '19.0.0.0.1',
    'depends': ['account_baseline',
                'l10n_co_bloodo',
                'account_cargowise_sync',
                ],
    'data': [
        # 'security/ir.model.access.csv',
        'reports/account_move_reports.xml',
        'reports/account_move_templates.xml',
        'views/account_account_views.xml',
        'views/res_company_view.xml',
        'views/account_move_views.xml',
    ],
}
