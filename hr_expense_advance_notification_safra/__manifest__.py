# -*- coding: utf-8 -*-
{
    'name': 'Notificación Aprobación Anticipo Safra',
    'summary': 'Envía notificación por correo al aprobar un anticipo a empleado',
    'description': '''
        Extiende hr_expense_baseline para enviar un correo electrónico automático
        al grupo contable cuando un anticipo a empleado es aprobado, solicitando
        el diligenciamiento del diario contable y fecha de registro.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Expenses',
    'license': 'OPL-1',
    'depends': [
        'hr_expense_baseline',
    ],
    'data': [
        'security/security_groups.xml',
        'data/mail_template_data.xml',
    ],
}
