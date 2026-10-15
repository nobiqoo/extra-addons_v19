# -*- coding: utf-8 -*-
{
    'name': 'Analytic Accounting',
    'summary': '''
        Module for defining analytic accounting object.
    ''',
    'description': '''
        - Module for defining analytic accounting object.
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': [
        'Juan Arcos juanparmer@gmail.com'
    ],
    'website': 'https://www.odone.com.co/',
    'category': 'Accounting/Accounting',
    'license': 'LGPL-3',
    'version': '19.0.0.1',
    'depends': [
        'account',
        'base_data_baseline',
        'hr_expense',
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'security/account_analytic_groups.xml',
        'views/account_analytic_view.xml',
        'views/product_category_view.xml',
        'views/product_template_view.xml',
        'views/account_analytic_plan_views.xml',
    ],
}
