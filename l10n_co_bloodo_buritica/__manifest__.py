{
    'name': "l10n co bloodo  Buritica",

    'summary': "Extend the electronic Invoice Report.",

    'description': """
        Add features in invoice electronic report.
    """,

    'author': "Odone S.A.S",
    'website': "https://www.odone.com.co",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting/Accounting',
    'application': True,
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['l10n_co_bloodo'],

    # always loaded
    'data': [
        'report/einvoicing_document_extended.xml'
    ],
}

