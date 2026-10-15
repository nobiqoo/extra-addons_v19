# -*- coding: utf-8 -*-
{
    'name': "Worksheet Template San Jorge",

    'summary': "Worksheet Template Module Extension for Euroden",

    'description': """
        - Creation of templates for quality control formats in quality inspection checkpoint for quality inspection.
        - Creation of format for packaging order
    """,

    'author': "Odone",
    'website': "https://www.odone.com.co",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Quality Control',
    'version': '19.0.0.0.1',
    'license':'GPL-3',

    # any module necessary for this one to work correctly
    'depends': ['hr_payroll_co','quality_control_worksheet', 'repair'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/worksheet_template_views.xml',
        'views/approval_quality_approvers.xml',
        'views/quality_point_views.xml',
        'views/quality_views.xml',
        'views/approval_role_views.xml',
        'report/inspection_release_format_template.xml',
        'report/refurbishment_format_template.xml',
        'report/biomedical_equipment_inspection_format_template.xml',
    ],
}
