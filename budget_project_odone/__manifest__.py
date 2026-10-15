# -*- coding: utf-8 -*-
{
    'name': "Budget project Odone",

    'summary': "This module adds a button on the project dashboard to know the budgets by budget situation",

    'version': '19.0.0.1.0',
    'author': 'ODONE SAS',
    'license': 'LGPL-3',

    'depends': ['project','account_budget_odone'],

    'data': [
        'views/crossovered_budget_line_views.xml',
        'views/crossovered_budget_views.xml'
    ]
}

