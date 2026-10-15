# -*- coding: utf-8 -*-
{
    'name': "Account Followup Baseline",

    'summary': "Extensión del módulo de seguimiento de cuentas",

    'description': """
        - Politica para activar o desacitvar el filtro de seguimiento de cuentas
        - Campo many2many para seleccionar las cuentas permitidas
        - Sobreescritura de método cron para modificar el seguimiento de cuentas
    """,

    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Followup',
    'version': '19.0.0.0.1',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['account_followup', 'account_reports'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
    ],
}

