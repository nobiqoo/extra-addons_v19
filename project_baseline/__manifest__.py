# -*- coding: utf-8 -*-
{
    'name': 'Project Baseline',
    'summary': '''
        - Solución Baseline para proyectos.
    ''',
    'description': '''
        - Pestaña de ingresos y gastos en las tareas de proyecto (Política).
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Services/Project',
    'version': '19.0.0.0.1',
    'depends': [
        'project',
        'sale',
        'purchase'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/res_config_settings_views.xml',
    ],
}
