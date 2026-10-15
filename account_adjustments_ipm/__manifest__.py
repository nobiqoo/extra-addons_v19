# -*- coding: utf-8 -*-
{
    'name': "Ajustes de Contabilidad para IPM",

    'summary': """
       Ajustes de Contabilidad para IPM""",

    'description': """
        - Adición de campo para reemplazar el campo de etiqueta en las facturas de cliente
        - Modificación de la plantilla de impresión de facturas de cliente para reflejar el nuevo campo
    """,

    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '19.0.0.0.1',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['l10n_co_bloodo'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'reports/account_move_templates.xml',
    ],

}
