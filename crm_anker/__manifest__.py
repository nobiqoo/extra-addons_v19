# -*- coding: utf-8 -*-
{
    'name': 'CRM Anker',
    'summary': '''
       Agrega campos para Anker
    ''',
    'description': '''
        - Agrega campos para Anker
    ''',
    'author': "OdOne S.A.S",
    'website': "https://www.odone.com.co/",
    'license': 'LGPL-3',
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'depends': [
        'crm',
    ],
    'data': [
        'security/crm_security.xml',
        'security/ir.model.access.csv',
        'views/crm_lead_database_views.xml',
        'views/crm_lead_industry_views.xml',
        'views/crm_lead_partner_type_views.xml',
        'views/crm_lead_service_views.xml',
        'views/crm_state_views.xml',
        'views/crm_lead_country_views.xml',
        'views/crm_lead_city_views.xml',
        'views/crm_lead_transport_views.xml',
        'views/crm_lead_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
}
