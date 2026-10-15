# -*- coding: utf-8 -*-
{
    'name': 'Expenses Odone',
    'summary': 'Extend the expenses module',
    'description': '''
        Extend the expenses module to include advance settings, petty cash management, and other features.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co',
    'version': '19.0.0.0.1',
    'category': 'Human Resources/Expenses',
    'license': 'OPL-1',
    'depends': [
        'hr_expense',
        'hr_expense_extract',
        'account_voucher',
        'account_baseline'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/hr_expense_sequence.xml',
        'data/ir_cron_data.xml',
        'wizard/hr_expense_wizard.xml',
        'wizard/petty_cash_open_wizard_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_journal_dashboard.xml',
        'views/hr_employee_views.xml',
        'views/hr_expense_advance_views.xml',
        'views/hr_expense_views.xml',
         'views/res_company.xml',
         'views/res_partner_views.xml',
        'security/ir_rule.xml',
    ],
}
