# -*- coding: utf-8 -*-
{
    'name': 'CargoWise Sync',
    'summary': '''
        Integración con CargoWise: campos consolcargo + lógica de sincronización.
    ''',
    'description': '''
        - Creación de terceros: CargoWise a Odoo.
        - Creación de Factura de Venta: CargoWise a Odoo.
        - Creación de Factura de Compra: CargoWise a Odoo.
        - Sincronización de estados de facturas hacia CargoWise.
        - Campos adicionales de operación logística en account.move.
        - Documentación interactiva disponible en la URL: /account_cargowise_sync/docs/ui
          (abrir esta ruta en su instancia de Odoo para ver Swagger UI).
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Accounting/Accounting',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'base_automation',
        'l10n_latam_base',
        'account_payment_order',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'data/l10n_latam_identification_type_data.xml',
        'data/base_automation_data.xml',
        'data/ir_cron_data.xml',
        'data/ir_actions_server_data.xml',
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
