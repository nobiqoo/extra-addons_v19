# -*- coding: utf-8 -*-
{
    'name': 'Account Payment Authorization Number Reconciliation',
    'summary': '''
        Mandatory bank authorization number on customer payments and automatic
        bank reconciliation matching based on it
    ''',
    'description': '''
        Adds a mandatory "Authorization Number" field on customer payments paid
        by bank transfer, card or payment link (Accounting, Point of Sale receipts
        and vouchers), and a matching field on bank statement lines (fillable from
        the Excel/CSV import), so the bank reconciliation engine can automatically
        reconcile a statement line with the corresponding customer payment whenever
        both numbers are exactly equal, without any user intervention.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.1.0.0',
    'depends': [
        'account',
        'account_accountant',
        'account_voucher',
        'point_of_sale',
    ],
    'data': [
        'views/account_payment_views.xml',
        'views/account_voucher_views.xml',
        'views/account_voucher_wizard_views.xml',
        'views/account_move_views.xml',
        'views/account_reconcile_model_views.xml',
        'views/account_bank_statement_line_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'account_payment_authorization_reconcile/static/src/app/models/pos_payment.js',
            'account_payment_authorization_reconcile/static/src/app/utils/order_payment_validation.js',
            'account_payment_authorization_reconcile/static/src/app/screens/payment_screen/payment_lines/payment_lines.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
