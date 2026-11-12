{
    'name': 'Arthome - Presupuestos comerciales y recaudo',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Metas mensuales, categorías, planificación semanal y cumplimiento',
    'author': 'OdOne S.A.S.',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'account'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/budget_views.xml',
        'views/customer_activity_views.xml',
        'data/customer_activity_cron.xml',
    ],
    'assets': {'web.assets_backend': [
        'sale_budget_arthome/static/src/dashboard.js',
        'sale_budget_arthome/static/src/dashboard.xml',
        'sale_budget_arthome/static/src/dashboard.scss',
    ]},
    'application': True,
    'installable': True,
}
