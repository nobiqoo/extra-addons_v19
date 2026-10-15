# -*- coding: utf-8 -*-
{
    'name': "Website helpdesk FL",

    'summary': "Campos en mesa de ayuda para fl",

    'description': """
    Este módulo personaliza y extiende los formularios de mesa de ayuda para fl
    """,

    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'version': '19.0.0.0.1',

    'depends': [
        'helpdesk',
        'mail',
        'project_enterprise',
        'website',
        'website_helpdesk',
        'project',
        'account',
        'hr',
        'base_address_extended',
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/attachments_security.xml',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/project_task_views.xml',
    ],
}
