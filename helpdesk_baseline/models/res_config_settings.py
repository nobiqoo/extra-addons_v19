# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    helpdesk_ticket_income_expense = fields.Boolean(
        'Income and Expense in helpdesk Tickets',
        related='company_id.helpdesk_ticket_income_expense',
        readonly=False
    )
