# -*- coding: utf-8 -*-
{
    'name': 'Colombian E-Invoicing for POS',
    'summary': '''
        Electronic envoicing for POS, direct integration with the DIAN.
    ''',
    'description': '''
        E.invoicing for POS
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': ['Bernardo David Lara Guevara <bdlgrw@gmail.com, bloodo.dev.solutions@gmail.com>'],
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Sales/Point of Sale',
    'version': '19.0.0.0.1',
    'depends': [
        'point_of_sale',
        'l10n_co_bloodo',
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'views/pos_order_views.xml',
        'views/pos_payment_method_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'l10n_co_pos_bloodo/static/src/store/**/*',
            'l10n_co_pos_bloodo/static/src/screens/payment_screen/**/*',
            'l10n_co_pos_bloodo/static/src/screens/receipt/**/*',
        ],
    }
}
