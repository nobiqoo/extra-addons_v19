# -*- coding: utf-8 -*-
{
    'name': 'CRM - Bamicol',
    'version': '19.0.1.0.0',
    'summary': 'Campo Arquitecto (Many2one contactos) en CRM y Ventas con obligatoriedad por equipo',
    'description': """
        Funcionalidades:
        • Campo architect_id (Many2one → res.partner) en crm.lead
        • Campo architect_id (Many2one → res.partner) en sale.order
        • Booleano require_architect en crm.team para configurar obligatoriedad
        • Extensión del análisis CRM (pivot, gráfico, búsqueda)
    """,
    'author': 'OdOne S.A.S',
    'contributors': ['Sebastian Cogollo <scogollo@odone.com.co>'],
    'website': 'https://www.odone.com',
    'category': 'Sales/CRM',
    'depends': ['crm', 'sale_crm'],
    'data': [
        'views/crm_team_views.xml',
        'views/crm_lead_views.xml',
        'views/sale_order_views.xml',
        'views/crm_lead_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
