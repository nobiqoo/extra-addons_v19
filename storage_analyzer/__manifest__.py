# -*- coding: utf-8 -*-
{
    'name': 'Storage Analyzer',
    'version': '19.0.1.0.0',
    'category': 'Technical/Tools',
    'summary': 'Análisis y monitoreo de consumo de almacenamiento Odoo',
    'description': """
Storage Analyzer
================

Módulo para analizar y reportar el consumo de almacenamiento en instancias Odoo.

Características:
---------------
* Monitoreo del tamaño de la base de datos PostgreSQL
* Análisis del filestore (archivos adjuntos)
* Detalle de consumo por modelo/tablas
* Histórico de crecimiento
* Dashboard visual con gráficos y KPIs
* Alertas configurables por umbral de almacenamiento

Uso:
----
1. Ir a Ajustes > Técnico > Análisis de Almacenamiento
2. Crear un nuevo análisis o esperar la ejecución automática (cron)
3. Revisar resultados en el dashboard

Desarrollado para empresas que implementan y dan soporte a múltiples proyectos Odoo SH.
""",
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co',
    'depends': ['base', 'web', 'mail', 'spreadsheet_dashboard'],
    'data': [
        'security/storage_security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/cron_jobs.xml',
        'data/dashboards.xml',
        'views/storage_analysis_views.xml',
        'views/storage_analysis_table_views.xml',
        'views/storage_analysis_attachment_views.xml',
        'views/storage_analysis_model_filetype_views.xml',
        'views/storage_analysis_trend_views.xml',
        'views/storage_config_settings_views.xml',
        'views/storage_analysis_report.xml',
        'views/storage_menus.xml',
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}