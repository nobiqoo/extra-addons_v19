# -*- coding: utf-8 -*-

{
    'name': 'Txt generator for bank payment',
    'summary': '''
        - It allows to generate TXT file to upload the payments to the banking portal
    ''',
    'description': '''
        - It allows to generate TXT file to upload the payments to the banking portal
    ''',
    'author': 'Bloodo by Bernardo D. Lara Guevara <bdlgrw@gmail.com>',
    'website': 'https://www.linkedin.com/in/bernardo-d-lara-guevara-2267a8142'
    '?lipi=urn%3Ali%3Apage%3Ad_flagship3_profile_view_base_contact_details'
    '%3BusuaZT0LSMGZWpv0e%2B0KLA%3D%3D',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    "version": "19.0.0.1",
    'depends': ['account_payment_order'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_bank_txt_config_views.xml',
        'views/account_payment_order_views.xml',
        'wizards/res_bank_txt_select_wizard_views.xml',
    ],
}
