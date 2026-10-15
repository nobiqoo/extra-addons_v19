# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.misc import frozendict
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _compute_partner_id(self):
        res = super(AccountMoveLine, self)._compute_partner_id()
        for line in self.filtered(lambda x: x.display_type == 'payment_term' and x.move_id.expense_id):
            line.partner_id = line.move_id.expense_id.employee_id.address_home_id.id
        return res

    @api.onchange('partner_id')
    def _inverse_partner_id(self):
        for line in self.filtered(lambda x: x.display_type == 'payment_term' and x.move_id.expense_id):
            if line.partner_id.id != line.move_id.expense_id.employee_id.address_home_id.id:
                line.partner_id = line.move_id.expense_id.employee_id.address_home_id.id
        return super(AccountMoveLine, self)._inverse_partner_id()
    
    def _compute_account_id(self):
        res = super(AccountMoveLine, self)._compute_account_id()
        term_lines = self.filtered(lambda ln: ln.display_type == 'payment_term' and ln.move_id.expense_id)
        for line in term_lines:
            expense_id = line.move_id.expense_id
            expense_journal = expense_id.expense_journal_id
            account_id = False
            if expense_id.type == 'advance':
                account_id = expense_journal.account_refund_expensive.id
            elif expense_id.type == 'expense_refund':
                account_id = expense_journal.account_refund_expensive.id
            elif expense_id.type == 'expense_petty_cash':
                account_id = expense_journal.account_refund_petty_cash.id
            if not account_id:
                raise ValidationError(
                    _("Configure the Refund expense account in journal settings.\n- %s", expense_journal.display_name)
                )
            line.account_id = account_id
        return res
