# -*- coding: utf-8 -*-
{
    "name": "Project ↔ Approvals Integration",
    "summary": "Vincula proyectos con requerimientos de aprobación y los muestra desde tareas",
    "version": "19.0.1.0.0",
    "category": "Project",
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    "license": "LGPL-3",
    "depends": ["project", "approvals", "purchase"],
    "data": [
        "views/approval_request_views.xml",
        "views/project_task_views.xml",
        "views/project_views.xml",
        'views/project_requirements_actions.xml',
    ],
    "installable": True,
    "application": False,
}
