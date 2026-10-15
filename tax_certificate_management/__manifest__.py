{
    'name': "Tax certificate management",
    'summary': "This module generates and requests tax certificates caused in the system",
    'description': "This module generates and requests tax certificates caused in the system",
    'version': '19.0.0.0.1',
    'depends': ['account', 'sale', 'base_address_extended'],
    "author": "OdOne S.A.S",
    "website": "http://www.odone.com.co",
    'license': 'LGPL-3',
    'category': 'Account',
    'description': """
       This module generates and requests tax certificates caused in the system
    """,
    # data files always loaded at installation
    'data': [
        'data/certificate_management_data.xml',
        'reports/withholding_certificate_report_template.xml',
        'reports/withholding_certificate_report_action.xml',
        'reports/mail_templates/certificate_report_email_template.xml',
        'views/account_move_line_extended_views.xml',
        'views/certificate_report_send_mail_views.xml',
        'views/withholding_certificate_report_views.xml',
        'views/withholding_certificate_type_views.xml',
        'views/certificate_period_views.xml',
        'views/withholding_certificates_wizard_views.xml',
        'security/ir.model.access.csv',
    ],
    "autoinstall": False,
    "installable": True,
}
