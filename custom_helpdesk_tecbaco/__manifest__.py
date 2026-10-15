# -*- coding: utf-8 -*-
{
    'name': "Custom helpdesk Tecbaco",

    'summary': "This module allows adding additional fields to the ticket, which will help with agent assignment as well as SLA policies.",

    'description': """
    This module adds different models to be related to the ticket, in order to determine the user in charge of the ticket based on the assignment rules created. Additionally, they allow taking other fields into account when creating SLA Policies.
    """,

    'author': 'ODONE SAS',

    'category': 'Services/Helpdesk',
    'version': '19.0.0.1.0',
    'license': 'OPL-1',

    'depends': ['helpdesk'],

    'data': [
        'security/ir.model.access.csv',
        'data/paperformat_helpdesk_ticket_report.xml',
        'views/views_custom_helpdesk_team.xml',
        'views/views_custom_helpdesk_ticket.xml',
        'views/views_helpdesk_assignment_rule.xml',
        'views/views_helpdesk_service_category.xml',
        'views/views_helpdesk_service_subcategory.xml',
        'views/views_helpdesk_service_type.xml',
        'views/views_helpdesk_support_type.xml',
        'views/views_helpdesk_zone.xml',
        'views/views_custom_helpdesk_sla.xml',
        'report/report_template.xml',
        'report/report_helpdesk_ticket.xml',
    ],
}
