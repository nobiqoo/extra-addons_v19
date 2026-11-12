# -*- coding: utf-8 -*-
{
    'name': 'Website Payroll',
    'summary': '''
        Website Payroll
    ''',
    'description': '''
        Website Payroll
    ''',
    'author': 'ODONE SAS',
    'website': 'https://www.odone.com.co',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'version': '19.0.0.0.0',
    'depends': [
        'website',
        'hr_payroll_co',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_leave.xml',
        'views/assets.xml',
        'views/hr_payroll_templates.xml',
        'views/hr_leave_type.xml',
        'views/hr_payslip_type_views.xml',
        'views/hr_leave_views.xml',
        'views/res_config_settings.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_hr_payroll/static/src/js/website_hr_payroll.js',
        ]
    },
}
