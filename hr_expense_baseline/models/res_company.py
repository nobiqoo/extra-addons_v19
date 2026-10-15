# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    advance_account_employee = fields.Many2one(
        'account.account', string='Advance Account for Employee'
    )
    refund_expense_account = fields.Many2one(
        'account.account', string='Refund Expense Account'
    )
    expenses_journal_id = fields.Many2one(
        'account.journal', string='Diario cruce de gastos'
    )
