# -*- coding: utf-8 -*-
{
    'name': 'HR migration',
    'summary': '',
    'description': '- Cron HR migration',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Hidden',
    'version': '19.0.0.0.0',
    'depends': ['hr_payroll_co'],
    'data': [
        'data/ir_cron.xml',
    ],
    "installable": True,
    "application": False,
}
