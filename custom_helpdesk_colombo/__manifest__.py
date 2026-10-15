# -*- coding: utf-8 -*-
{
    'name': "Custom Helpdesk Colombo Americano",

    'summary': "Adds a responsible/guardian contact and phone number to helpdesk tickets.",

    'description': """
    This module adds the fields 'Responsable o Acudiente' and 'Teléfono del Responsable o Acudiente' to the helpdesk ticket form, specific to Colombo Americano.
    """,

    'author': 'ODONE SAS',

    'category': 'Services/Helpdesk',
    'version': '19.0.0.1.0',
    'license': 'OPL-1',

    'depends': ['helpdesk'],

    'data': [
        'views/helpdesk_ticket_views.xml',
    ],
}
