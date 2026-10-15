{
    'name': "Product tariff code Adipack",

    'summary': "Module to add a tariff code in the product and show it in the graphic representation of the electronic invoice.",

    'description': """
Module to add a tariff code in the product and show it in the graphic representation of the electronic invoice.""",

    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Inventory',
    'version': '19.0.1.0.0',

    'depends': ['product','l10n_co_bloodo'],

    # always loaded
    'data': [
        'views/product_template_views.xml',
        'reports/account_move_templates.xml',
    ],
   
}

