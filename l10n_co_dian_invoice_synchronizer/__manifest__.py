# -*- coding: utf-8 -*-
{
    'name': "l10n_co_dian_invoice_synchronizer",

    'summary': "Electronic invoice synchronizer with the Colombian DIAN",

    'description': """
DIAN Electronic Invoice Synchronizer - Colombia
================================================

Imports received documents from the DIAN catalog using a token URL obtained
from DIAN. Synchronization records show imported, skipped and mapping-error
counts. Documents can be linked to purchase orders and vendor bills.

XML download is currently unavailable because DIAN protects the ZIP endpoint
with a browser challenge. The module imports the catalog data only.
    """,

    'author': "OdOne S.A.S",
    'website': "https://www.odone.com.co/",

    'category': 'Accounting/Localizations',
    'version': '19.0.1.0.0',
    'countries': ['co'],

    'depends': [
        'account',
        'accountant',
        'purchase',
        'l10n_co_bloodo',
    ],

    'data': [
        'security/ir.model.access.csv',
        'security/dian_sync_security.xml',

        'data/l10n_co_dian_invoice_synchronizer.xml',
        'views/dian_document_views.xml',
        'views/dian_sync_views.xml',

        'wizards/dian_invoice_synchronizer.xml',
        'wizards/dian_document_link_purchase_order_wizard.xml',
    ],
    
    'license': 'LGPL-3',
}
