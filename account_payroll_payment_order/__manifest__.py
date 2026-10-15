# -*- coding: utf-8 -*-
{
    'name': "Ordenes de pago de nómina",

    'summary': """
        Permite filtrar por procesamientos de nómina y banco para crear ordenes de pago
    """,


    'author': "OdOne S.A.S",
    'website': "https://www.odone.com.co/",


    "category": "Banking addons",
    'version': '19.0.0.1',
    'license': 'LGPL-3',

    'depends': ['account_payment_order', 'hr_payroll_co'],

    'data': [
        'wizard/account_payment_line_create_view.xml'
    ],
}
