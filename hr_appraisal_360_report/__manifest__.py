# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Informe 360 de Evaluaciones',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Informe masivo de retroalimentaciones 360 con filtros y exportación a Excel',
    'author': 'Custom Development',
    'website': 'https://www.odoo.com',
    'depends': [
        'hr_appraisal',
        'hr_appraisal_survey',
        'base',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/hr_appraisal_360_report_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'assets': {},
}
