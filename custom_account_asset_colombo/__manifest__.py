# -*- coding: utf-8 -*-
{
    'name': "Custom Account Asset Colombo Americano",

    'summary': "Adds the 'Valor IVA' field to the fixed asset form.",

    'description': """
    This module adds the 'Valor IVA' field to the "Other Information" tab of the fixed asset form, specific to Colombo Americano.
    """,

    'author': 'ODONE SAS',

    'category': 'Accounting/Accounting',
    'version': '19.0.0.1.0',
    'license': 'OPL-1',

    'depends': ['account_asset_ifrs'],

    'data': [
        'views/account_asset_views.xml',
    ],
}
