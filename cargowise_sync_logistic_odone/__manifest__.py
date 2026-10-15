# -*- coding: utf-8 -*-
{
    'name': 'Integración con CargoWise por OdOne',
    'summary': '''
        Integración con CargoWise.
    ''',
    'description': '''
        - Creación de terceros: CargoWise a Odoo.
        - Creación de Factura de Venta: CargoWise a Odoo.
        - Creación de Factura de Compra: CargoWise a Odoo.
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': 'Bernardo D. Lara Guevara bdlgrw@gmail.com',
    'website': 'https://www.odone.com.co/',
    'category': 'Technical',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        # 'contacts',
        # 'l10n_co',
        # 'base_automation',
        # 'l10n_latam_base',
        'account_logistic_odone',
        'l10n_co_data_bloodo',
    ],
    'data': [
        'security/ir.model.access.csv',
        # 'data/res.country.state.csv',
        'data/ir_config_parameter_data.xml',
        # 'data/l10n_latam_identification_type_data.xml',
        'data/ir_cron_data.xml',
        'data/ir_actions_server_data.xml',
        # 'data/base_automation_data.xml',
        # 'data/res_country_state_data.xml',
        'views/l10n_latam_identification_type_views.xml',
        'views/res_company_views.xml',
        'views/res_country_state_views.xml',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'views/account_journal_views.xml',
        'views/invoice_cw_log_views.xml',
        'views/account_move_views.xml',
        'views/cw_template.xml',
    ],
}
