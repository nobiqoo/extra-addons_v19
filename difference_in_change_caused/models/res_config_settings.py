# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    income_currency_exchange_account_made_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.income_currency_exchange_account_made_id",
        string="Realized Gain Exchange Rate Account",
        readonly=False,
        check_company=True,
        domain="[('internal_group', '=', 'income')]")
    expense_currency_exchange_account_made_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.expense_currency_exchange_account_made_id",
        string="Realized Loss Exchange Rate Account",
        readonly=False,
        check_company=True,
        domain="[('account_type', 'in', ('expense', 'expense_other'))]")
