# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Budget Management - Odone',
    'category': 'Accounting/Accounting',
    'description': """
Use budgets to compare actual with expected revenues and costs
--------------------------------------------------------------
""",
    'depends': ['account','account_accountant','purchase_approval'],
    'data': [
        'security/ir.model.access.csv',
        'security/account_budget_security.xml',
        'views/account_budget_views.xml',
        'views/account_analytic_account_views.xml',
        'views/account_move_views.xml',
        'views/purchase_approval_budget_wizard_views.xml',
        'views/purchase_appoval_reason_budget_wizard_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'account_budget_odone/static/src/js/budget_list_renderer.js',
            'account_budget_odone/static/src/js/budget_list_renderer.xml',
        ],
    },
    'version': '19.0.0.1.0',
    'author': 'ODONE SAS',
    'license': 'OPL-1',


}
