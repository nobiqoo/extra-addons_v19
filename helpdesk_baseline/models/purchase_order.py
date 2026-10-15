# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    ticket_id = fields.Many2one('helpdesk.ticket',
                                'Helpdesk Ticket',
                                copy=False)
    helpdesk_ticket_income_expense = fields.Boolean(
        'Income and Expense in helpdesk Tickets',
        related='company_id.helpdesk_ticket_income_expense'
    )
