# -*- coding: utf-8 -*-
{
    'name': 'PyG por Posición',
    'summary': 'Reportes PyG por posición (P&L) e Informe de Comisiones',
    'description': '''
        - PyG por posición: reporte de P&L por cuenta analítica/posición.
        - P&G por posición (Dinámico): wizard con filtros dinámicos.
        - P&G por posición (Filtros): gestión de plantillas de filtros.
        - Informe de Comisiones: reporte analítico con estados de cuenta analítica.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Accounting/Accounting',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'account_cargowise_sync',
        'report_xlsx',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pyg_report_security.xml',
        'data/ir_actions_server_data.xml',
        'views/pyg_report_views.xml',
        'views/pyg_position_report_filter_views.xml',
        'views/pyg_analytic_report_views.xml',
        'reports/pyg_position_reports.xml',
        'reports/pyg_position_report_template.xml',
        'wizards/pyg_position_wizard_views.xml',
        'wizards/pyg_analytic_position_wizard_views.xml',
        'views/pyg_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_pyg/static/src/js/pyg_position_filter.js',
            'account_pyg/static/src/xml/pyg_position_filter.xml',
            'account_pyg/static/src/css/table.css',
        ],
    },
}
