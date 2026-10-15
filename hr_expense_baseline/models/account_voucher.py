# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountVoucherWizardInherit(models.TransientModel):
    _inherit = 'account.voucher.wizard'

    def button_create_voucher(self):
        model = self.env.context.get('active_model')
        ids = self.env.context.get('active_ids')
        if not model:
            return False

        actives = self.env[model].browse(ids)
        for active in actives:
            if active.move_type not in ('out_invoice', 'in_invoice', 'out_receipt', 'in_receipt'):
                continue
            if active.payment_state == 'paid':
                continue

            is_customer_document = active.move_type in ('out_invoice', 'out_receipt')
            values = {
                'voucher_type': 'voucher',
                'partner_type': is_customer_document and 'customer' or 'supplier',
                'company_id': active.company_id.id,
                'partner_id': active.partner_id.id,
                'journal_id': self.journal_id.id,
                'account_id': is_customer_document and active.partner_id.property_account_receivable_id.id or active.partner_id.property_account_payable_id.id,
                'date': self.date,
                'amount': self.active_bool and active.amount_residual or self.amount,
                'currency_id': self.active_bool and active.currency_id.id or self.currency_id.id,
                'voucher_date': self.date,
                'voucher_reference': self.active_bool and active.name or self.voucher_reference,
            }
            voucher = self.env['account.voucher'].create(values)
            voucher.with_context(line_ids=active.line_ids.ids).compute_line_ids()
            voucher.action_post()
        return True


class AccountVoucherInherit(models.Model):
    _inherit = 'account.voucher'

    def _line_dictionary(self, move_line, amount, amount_original, amount_unreconciled):
        line = super(AccountVoucherInherit, self)._line_dictionary(
            move_line, amount, amount_original, amount_unreconciled)

        line['expense_id'] = move_line.expense_id.id if move_line.expense_id else False

        return line

    # def action_post(self):
    #     res = super(AccountVoucherInherit, self).action_post()
    #     self._update_petty_cash_fund()
    #     return res

    def _update_petty_cash_fund(self):
        for line in self.line_passive_ids:
            expense_id = line.move_line_id.move_id.expense_id
            if expense_id and expense_id.petty_cash_responsible_id:
                petty_cash_journal = expense_id.expense_journal_id
                if petty_cash_journal and petty_cash_journal.petty_cash:
                    new_fund_value = petty_cash_journal.fund + line.amount
                    petty_cash_journal.sudo().write({'fund': new_fund_value})

    def _prepare_move_id(self):
        line = super(AccountVoucherInherit, self)._prepare_move_id()

        line['expense_id'] = self.line_passive_ids.expense_id.id

        return line

    def _line_dictionary_move_id(self, amount, amount_currency):
        line = super(AccountVoucherInherit, self)._line_dictionary_move_id(
            amount, amount_currency)

        line['expense_id'] = self.line_passive_ids.expense_id.id if self.line_passive_ids.expense_id else False

        return line

    def _line_dict_writeoff_move_id(self, writeoff_amount, amount_currency):
        line = super(AccountVoucherInherit, self)._line_dict_writeoff_move_id(
            writeoff_amount, amount_currency)

        line['expense_id'] = self.line_passive_ids.expense_id.id if self.line_passive_ids.expense_id else False

        return line
    
    def action_post(self):
        res = super(AccountVoucherInherit, self).action_post()
        self._update_petty_cash_fund()

        for voucher in self:
            move_ids = (voucher.line_passive_ids | voucher.line_active_ids).mapped(
                'move_line_id.move_id'
            )
            advances = self.env['hr.expense'].search([
                ('account_move_id', 'in', move_ids.ids),
                ('advance_id', '!=', False),
            ]).mapped('advance_id')

            if not voucher.partner_id:
                for advance in advances:
                    advance.recompute_legalization_state()
                continue

            advances |= self.env['hr.expense.advance'].search([
                ('employee_id.address_home_id', '=', voucher.partner_id.id),
                ('state', '=', 'pending_legalization'),
            ])

            for advance in advances:
                advance.recompute_legalization_state()

        return res


class AccountVoucherLineInherit(models.Model):
    _inherit = 'account.voucher.line'

    expense_id = fields.Many2one(
        comodel_name='hr.expense',
        string='Expense'
    )
