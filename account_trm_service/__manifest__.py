# -*- coding: utf-8 -*-

{
    'name': 'Servicio TRM Superintendencia Financiera',
    'summary': 'TRM tomada desde la Superintendencia de Industria y Comercio',
    'author': "OdOne S.A.S.",
    'contributors': ["Jorge Cerquera jorgeandresc05@gmail.com"],
    'website': "https://www.odone.com.co/",
    'category': 'Accounting/Accounting',
    'version': '19.0.0.0.1',
    'license': 'AGPL-3',
    'depends': [
        'account',
    ],
    'description': '''

TRM tomada desde la Superintendencia de Industria y Comercio
========================

''',
    'data': [
        'data/ir_cron.xml',
        'views/res_company_view.xml',
    ],
    'qweb': [
    ]
}
