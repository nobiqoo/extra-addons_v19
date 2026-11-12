# -*- coding: utf-8 -*-
{
    'name': 'Integración de Biométricos ZKTeco (ADMS / Cloud Server)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': "Sincronización en tiempo real de asistencias con dispositivos ZKTeco (SpeedFace V4/V5, Horus, MB10, SenseFace) vía protocolo PUSH / ADMS.",
    'description': """
Módulo de Integración Biométrico ZKTeco (ADMS / PUSH Protocol)
==============================================================
Permite conectar biométricos ZKTeco modernos que operan bajo protocolo en la nube (ADMS / Cloud Server)
hacia Odoo en tiempo real mediante peticiones HTTP.

Características:
----------------
* Recepción de marcaciones en tiempo real por endpoints estándar (/iclock/cdata y /iclock/getrequest).
* Cero necesidad de abrir puertos o NAT en la oficina del cliente.
* Sincronización inteligente y reactiva de usuarios (Opción C: Inhabilitación en rotaciones, Eliminación en bajas).
* Acciones masivas desde vista de empleados y wizard centralizado multi-biométrico.
* Algoritmo de agrupación por sesiones (soporta turnos rotativos y nocturnos).
* Deduplicación por Hash SHA-1 estricto e idempotente.
* Registro completo en Marcaciones en Crudo y generación de Entrada/Salida en Asistencias nativas (hr.attendance).
* Cola de comandos remotos en tiempo real.
    """,
    'author': 'George J Ramirez',
    'company': 'GJRM Servicios Tecnologicos',
    'maintainer': 'George J Ramirez (GJRM Servicios Tecnologicos)',
    'website': "#",
    'depends': ['base_setup', 'hr_attendance'],
    'external_dependencies': {
        'python': ['pyzk'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/biometric_device_details_views.xml',
        'views/biometric_raw_punch_views.xml',
        'views/daily_attendance_views.xml',
        'views/biometric_mapping_views.xml',
        'views/biometric_user_mapping_wizard_views.xml',
        'views/biometric_odoo_to_biometric_wizard_views.xml',
        'views/biometric_employee_mass_sync_wizard_views.xml',
        'views/biometric_edit_users_menu_wizard_views.xml',
        'views/hr_employee_views.xml',
        'views/biometric_device_attendance_menus.xml',
        'data/biometric_cron.xml',
    ],
    'images': ['static/description/icon.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
