# -*- coding: utf-8 -*-
{
    'name': 'Voucher Account',
    'summary': '''
        Voucher Account
    ''',
    'description': '''
        - falta descripcion.
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': [
        'Juan Arcos juanparmer@gmail.com'
    ],
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.0.0.1',
    'depends': [
        'sale',
        'contacts'
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'security/res_groups_security.xml',
        "security/ir_rule_security.xml",
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/account_voucher_line_views.xml',
        'views/account_voucher_views.xml',
        'views/account_payment_term_views.xml',
        'views/account_journal_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/account_voucher_wizard_views.xml',
        'report/account_voucher_reports.xml',
        'views/account_voucher_customer_template.xml',
        'views/account_voucher_supplier_template.xml',
        'views/generic_accounting_receipt_template.xml',
        'views/purchase_order_views.xml',
        'views/voucher_mail_error_views.xml',
        'views/account_loan_views.xml',
        'data/mail_template_voucher_data.xml',
    ],
    'installable': True,
}
