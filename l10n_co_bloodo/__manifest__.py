# -*- coding: utf-8 -*-
{
    'name': 'Colombian E-Invoicing and Document Support',
    'summary': '''
        Electronic invoicing, supporting document and events,
         direct integration with the DIAN.
    ''',
    'description': '''
        Direct integration with DIAN
        - Direct electronic invoicing.
        - Direct support document.
        - Direct events, Resolution 85.
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': ['Bernardo David Lara Guevara <bdlgrw@gmail.com, bloodo.dev.solutions@gmail.com>'],
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Accounting/Localizations/EDI',
    'version': '19.0.0.0.1',
    'depends': [
        'account',
        'l10n_co',
        'l10n_latam_base',
        'uom',
        'account_debit_note',
        'account_journal_sequence',
        'l10n_co_data_bloodo',
        'resource',
        'base_address_extended',
    ],
    'data': [
        'security/l10n_co_bloodo_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/ir_actions_server_data.xml',
        'data/ir_config_parameter_data.xml',
        'views/account_move_line_views.xml',
        'views/account_move_views.xml',
        'views/ir_sequence_views.xml',
        'views/account_journal_views.xml',
        'views/res_company_views.xml',
        'views/dian_email_templates.xml',
        'views/dian_event_email_templates.xml',
        'views/history_dian_event_views.xml',
        'views/consignment_data_views.xml',
        'wizards/account_move_reversal_views.xml',
        'wizards/account_debit_note_views.xml',
        'wizards/invoice_import_wizard_views.xml',
        'wizards/xml_by_document_key_wizard_views.xml',
        'wizards/dian_event_send_wizard_views.xml',
        'wizards/send_dian_result_wizard_views.xml',
        'reports/account_move_reports.xml',
        'reports/account_move_templates.xml',
    ],
    'installable': True,
    'assets': {
        'web.assets_backend': [
            'l10n_co_bloodo/static/src/css/ei_group.css',
        ],
    },
    'external_dependencies': {
        'python': [
            'unidecode',
            'xmlsig',
            'jinja2',
            'OpenSSL',
            'xades',
            'qrcode',
            'pgxades'
        ],
    }
}
