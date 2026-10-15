# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PettyCashOpen(models.TransientModel):
    _name = 'petty.cash'
    _description = 'petty.cash'

    operation_type = fields.Selection(
        [
            ("open", "Open"),
            ("increase", "Increase"),
            ("decrease", "Decrease"),
            ("close", "Close"),
        ]
    )

    partner_id = fields.Many2one("res.partner", domain=[
                                 ('petty_cash_manager', '=', True)])
    amount = fields.Float()

    def button_accept(self):
        if self.operation_type != 'close':
            if self.amount <= 0:
                raise UserError(_('The amount must be positive.'))
        if self.operation_type == "open":
            if self.partner_id.petty_cash_opened:
                raise UserError(
                    _("This partner already has a petty cash open."))
            move_id = self.create_account_entry()
            self.partner_id.write({'petty_cash_opened': True})
            return self.action_view_move(move_id)
        elif self.operation_type in ["increase", "decrease", "close"]:
            if self.operation_type == "decrease":
                if self.amount > self.partner_id.petty_cash_journal.fund:
                    raise UserError(
                        -("Amount don't must be greater than fund in journal")
                    )
            if not self.partner_id.petty_cash_opened:
                raise UserError(
                    _("This partner does not have a petty cash open."))
            move_id = self.create_account_entry()
            return self.action_view_move(move_id)

    def create_account_entry(self):
        self.ensure_one()
        journal_id = self.partner_id.petty_cash_journal
        if not journal_id:
            raise UserError(
                _('No petty cash journal defined for this partner.'))

        if self.operation_type in ["open", "increase"]:
            debit_account_id = journal_id.default_account_id.id
            credits_account_id = journal_id.account_payable_cash.id
            journal_id.sudo().write({'fund': journal_id.fund + self.amount})
        else:
            debit_account_id = journal_id.account_refund_petty_cash.id
            credits_account_id = journal_id.default_account_id.id
            if self.operation_type == "close":
                self.amount = journal_id.fund
                self.partner_id.write({'petty_cash_opened': False})
            if journal_id.fund >= self.amount:
                journal_id.sudo().write(
                    {'fund': journal_id.fund - self.amount})
            else:
                raise UserError(_('Insufficient funds to decrease.'))
        
        if not debit_account_id or not credits_account_id:
            raise UserError(_(
                'El diario no tiene definidas las siguientes cuentas:\n%s\n%s',
                '- Cuenta de efectivo' if not debit_account_id else '',
                '- Cuenta por pagar caja menor' if not journal_id.account_payable_cash else 
                '- Cuenta reemboldo de caja menor' if not journal_id.account_refund_petty_cash else
                ''))

        account_move = self.env['account.move'].create({
            'partner_id': self.partner_id.id,
            'journal_id': journal_id.id,
            'date': fields.Date.context_today(self),
            'line_ids': [
                (0, 0, {
                    'account_id': debit_account_id,
                    'partner_id': self.partner_id.id,
                    'debit': self.amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': credits_account_id,
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': self.amount,
                }),
            ],
        })
        account_move.action_post()

        return account_move.id

    def action_view_move(self, move_id):
        action = self.env.ref('account.action_move_journal_line').read()[0]
        form_view = [(self.env.ref('account.view_move_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + \
                [(state, view)
                 for state, view in action['views'] if view != 'form']
        else:
            action['views'] = form_view
        action['res_id'] = move_id
        return action
