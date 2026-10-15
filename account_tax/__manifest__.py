# -*- coding: utf-8 -*-
{
    'name': "Account Tax",
    'summary': "Account Tax",
    'description': '''
        Caracteristicas:
        - Cálculo de impuestos con base mímina o por ciudad
        - CIIU
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': ['Juan Arcos, juanparmer@gmail.com'],
    'website': 'https://www.odone.com.co',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.0.0.1',
    'depends': [
        'account',
        'base_address_extended',
        'contacts',
        'purchase',
        'sale',
    ],
    'data': [
        'data/res.partner.classification.csv',
        'data/ir_ui_menu_data.xml',
        'security/ir.model.access.csv',
        'security/account_tax_security.xml',
        'views/account_move_view.xml',
        'views/account_tax_view.xml',
        'views/product_category_view.xml',
        'views/purchase_order_view.xml',
        'views/res_city_view.xml',
        'views/res_partner_view.xml',
        'views/sale_order_view.xml',
        'views/res_config_settings_view.xml',
    ],
}
