# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    voucher_debit_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Expense Receipts Account',
        check_company=True,
        copy=False,
        ondelete='restrict',
        domain=[('active', '=', True), ('account_type',
                                             'not in', ('asset_receivable', 'liability_payable'))]
    )
    voucher_credit_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Expense Vouchers Account',
        check_company=True,
        copy=False,
        ondelete='restrict',
        domain=[('active', '=', True), ('account_type',
                                             'not in', ('asset_receivable', 'liability_payable'))]
    )
    conditions_tax = fields.Text(string='Condiciones tributarias')

    def _prepare_voucher_data(self):
        return {
            'account_debit': self.voucher_debit_account_id,
            'account_credit': self.voucher_credit_account_id
        }
