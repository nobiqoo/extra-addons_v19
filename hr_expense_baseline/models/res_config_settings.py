# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    advance_account_employee = fields.Many2one(
        related='company_id.advance_account_employee',
        readonly=False,
        comodel_name='account.account',
        string='Advance Account for Employee'
    )
    refund_expense_account = fields.Many2one(
        related='company_id.refund_expense_account',
        readonly=False,
        comodel_name='account.account',
        string='Refund Expense Account'
    )
