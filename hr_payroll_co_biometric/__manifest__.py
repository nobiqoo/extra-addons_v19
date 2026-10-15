# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Turnos',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Gestión integral de turnos, asistencia y control biométrico integrado con nómina colombiana.',
    'description': """
        Módulo que integra la gestión de turnos laborales con los dispositivos biométricos ZKTeco
        y la nómina colombiana. Permite planificar turnos, validar asistencia real versus programada,
        detectar novedades (tardanzas, ausencias, horas extras) y aplicarlas automáticamente
        en la nómina, cumpliendo con la legislación laboral colombiana.
    """,
    'author': 'OdOne S.A.S',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',

    'depends': [
        'hr_payroll_co',
        'hr_zk_attendance',
        'web_gantt',
    ],

    'external_dependencies': {'python': ['openpyxl', 'xlsxwriter']},

    'data': [
        # Seguridad
        'security/security.xml',
        'security/ir.model.access.csv',

        # Datos iniciales
        'data/hr_shift_type_data.xml',
        'data/ir_cron_data.xml',
        'data/economic_variables_data.xml',
        'data/hr_overtime_rules_data.xml',

        # Vistas - Turnos
        'views/hr_shift_views.xml',
        'views/hr_shift_schedule_views.xml',

        # Vistas - Asistencia
        'views/hr_attendance_record_views.xml',
        'views/hr_attendance_novelty_views.xml',

        # Vistas - Configuración
        'views/hr_overtime_rule_views.xml',
        'views/res_config_settings_views.xml',

        # Documentación
        'views/documentation_views.xml',

        # Wizards
        'wizards/hr_process_attendance_wizard_views.xml',
        'wizards/hr_import_shifts_excel_wizard_views.xml',

        # Reportes
        'reports/hr_overtime_report_views.xml',
        'reports/hr_overtime_report_template.xml',

        # Menús (al final)
        'views/menus.xml',
    ],

    'post_init_hook': 'post_init_hook',

    'installable': True,
    'auto_install': False,
    'application': False,
}
