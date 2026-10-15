# -*- coding: utf-8 -*-
{
    'name': 'Support Document for Expenses',
    'summary': '''
        Supporting document for legalization of expenses
    ''',
    'description': '''
        - Direct support document.
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': ['Bernardo David Lara Guevara <bdlgrw@gmail.com, bloodo.dev.solutions@gmail.com>'],
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Accounting/Localizations/EDI',
    'version': '19.0.0.0.1',
    'depends': [
        'hr_expense_baseline',
        'l10n_co_bloodo'
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'views/hr_expense_views.xml',
    ],
}

