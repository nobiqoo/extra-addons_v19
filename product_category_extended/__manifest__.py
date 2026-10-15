{
    'name': "Product category extended",
    'summary': "Product category extended",
    'description': "Product category extended",
    'version': '19.0.0.0.1',
    'depends': ['product', 'mrp'],
    'author': 'OdOne S.A.S.',
    "website": "http://www.odone.com.co",
    'category': 'Inventory/Inventory',
    'description': """
       In this module is added fields to product and develop functionality for reference
    """,
    # data files always loaded at installation
    'data': [
        "security/ir.model.access.csv",
        'views/product_attribute_value_view.xml',
        'views/product_category_view.xml',
        'views/product_template_view.xml',
        'views/res_company.xml',
        'data/product_template_data.xml',
    ],
    "autoinstall": False,
    "installable": True,
    "license": 'LGPL-3',
}
