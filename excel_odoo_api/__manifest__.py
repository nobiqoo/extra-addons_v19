# -*- coding: utf-8 -*-
{
    'name': 'Table generator for excel',
    'summary': '''
    ''',
    'description': '''
        - Table generator for excel ODC
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Reporting',
    'version': '19.0.0.0.1',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/excel_odoo_api_groups.xml',
        'views/excel_data_search_views.xml',
        'views/excel_data_search_templates.xml'
    ],
}
