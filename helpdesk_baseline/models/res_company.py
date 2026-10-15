# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    helpdesk_ticket_income_expense = fields.Boolean(
        'Income and Expense in helpdesk Tickets',
        help='Allows to manage income and expenses from help desk tickets.'
    )
