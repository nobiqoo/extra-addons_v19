# -*- coding: utf-8 -*-
{
    'name': 'Nómina Electrónica Colombiana',
    'summary': '''
        Nómina Electrónica Colombiana de acuerdo a la normatividad de la DIAN
    ''',
    'description': '''
        - Nómina Electrónica Colombiana de acuerdo a la normatividad de la DIAN
    ''',
    'author': 'Bernardo David Lara Guevara - bdlgrw@gmail.com',
    'website': '',
    'license': 'OPL-1',
    'category': 'Human Resources',
    'version': '19.0.0.0.1',
    'depends': [
        'hr_payroll_co',
        'l10n_co_data_bloodo'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/edi_hr_processing_security.xml',
        'security/edi_hr_document_security.xml',
        'data/ir_sequence_data.xml',
        'data/ir_actions_server_data.xml',
        'data/ir_cron_data.xml',
        'data/dian_concept_type_data.xml',
        'views/hr_payslip_views.xml',
        'views/res_company_views.xml',
        'views/edi_hr_document_views.xml',
        'views/edi_hr_processing_views.xml',
        'views/dian_concept_type_views.xml',
        'views/hr_overtime_type_views.xml',
        'views/hr_novelty_type_views.xml',
        'views/hr_concept_views.xml',
        'views/menuitems.xml',
    ],
}
