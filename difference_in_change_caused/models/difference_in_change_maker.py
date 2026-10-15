
# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError
import ast


class DifferenceInChangeMaker(models.Model):
    _name = 'difference.in.change.maker'
    _description = 'Difference in change maker'

    name = fields.Char(
        string="Name",
        default='/',
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        string="Company",
        required=True
    )
    cut_date = fields.Date(
        string='Cut date',
        required=True
    )
    foreign_currency_id = fields.Many2one(
        'res.currency',
        string="Foreign currency",
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string="Company currency",
    )
    accounts_ids = fields.Many2many(
        'account.account',
        string="Accounts",
        domain="""[('reconcile', '=', True),
            ('account_type', 'in', ['asset_receivable','liability_payable'])]"""
    )
    other_accounts_ids = fields.Many2many(
        comodel_name='account.account',
        relation='difference_in_change_and_other_accounts_table',
        string="Other Accounts",
        domain=""" [('account_type', 'not in', ['asset_receivable','liability_payable'])] """
    )
    move_lines_ids = fields.Many2many(
        'account.move.line',
        string="Moves to process",
        copy=False
    )
    trm_amount = fields.Monetary(string="TRM", copy=False,)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
        ('reverted', 'Moves reversed'),
    ], string='State',
        default='draft',
        required=True
    )
    exchange_move_ids = fields.One2many(
        'account.move',
        'exchange_id',
        string="Exchange moves"
    )
    moves_count = fields.Integer(
        string="Moves count",
        compute='_compute_moves_count'
    )
    date_in_moves = fields.Date(
        string="Date in moves",
        help='This date will be applied in moves to create'
    )
    document_type = fields.Selection([
        ('account', 'Account'),
        ('movement', 'Movement')
    ], string='Document type', default='movement')

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = '/'
        return super().copy(default)

    def _compute_moves_count(self):
        for record in self:
            record.moves_count = len(record.exchange_move_ids)

    def action_view_moves(self):
        self.ensure_one()
        move_ids = self.exchange_move_ids.ids
        result = self.env['ir.actions.act_window']._for_xml_id(
            'account.action_move_journal_line')
        if len(move_ids) > 1:
            result['domain'] = [('id', 'in', move_ids)]
            if 'context' in result:
                context = ast.literal_eval(result['context'])
                if 'search_default_posted' in context:
                    del context['search_default_posted']
                    result['context'] = context
        elif len(move_ids) == 1:
            result['views'] = [
                (self.env.ref('account.view_move_form', False).id, 'form')]
            result['res_id'] = move_ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    def get_move_lines_with_residual(self):
        query = """ select aml.id as id
            from account_move_line aml
                inner join account_account acc on acc.id = aml.account_id
        where aml.date <= '{cut_date}'
            and aml.currency_id = {currency_id}
            and abs(aml.amount_residual_currency) > 0
            and aml.company_id = {company_id}
            and aml.parent_state = 'posted'
        """.format(
            cut_date=str(self.cut_date),
            currency_id=self.foreign_currency_id.id,
            company_id=self.company_id.id
        )
        if self.document_type == 'movement':
            account_ids = self.accounts_ids
        else:
            account_ids = self.other_accounts_ids

        if len(account_ids) > 0:
            tuple_accounts = str(tuple(account_ids.ids)) if len(
                account_ids) > 1 else '(' + str(account_ids[0].id) + ')'
            query += " and acc.id in %s" % (str(tuple_accounts))
        self._cr.execute(query)
        report_data = self._cr.dictfetchall()
        return report_data

    def extract_invoices_with_balance(self):
        self.validate_trm()
        report_data = self.get_move_lines_with_residual()
        if len(report_data) > 0:
            move_line_ids = [line['id'] for line in report_data]
            self.move_lines_ids = [((6, 0, move_line_ids))]
        else:
            raise ValidationError(_('No movements found for these options.'))
        for move_line in self.move_lines_ids:
            amount_to_exchange = 0
            trm = self.trm_amount
            move_line_rate = abs(move_line.amount_residual /
                                 move_line.amount_residual_currency)
            move_line_rate = self.company_id.currency_id.round(move_line_rate)
            amount_to_exchange = (trm*move_line.amount_residual_currency -
                                  move_line_rate*move_line.amount_residual_currency)
            move_line.current_exchange_rate = move_line_rate
            move_line.amount_to_exchange = amount_to_exchange
        self.state = 'computed'

    def validate_trm(self):
        if self.trm_amount <= 0:
            raise ValidationError(_('The TRM must be grater than zero.'))

    def validate_move_date(self):
        if not self.date_in_moves:
            raise ValidationError(_('Must be write the move date.'))

    def get_move_lines_vals(self, credit_account, debit_account, amount, am, move_name):
        aml_vals = [
            {
                'amount_residual': 0,
                'account_id': credit_account.id,
                'balance': 0,
                'credit': 0,
                'debit': 0,
                'ifrs_balance': -amount,
                'ifrs_credit': amount,
                'ifrs_debit': 0,
                'ifrs_type': 'ifrs',
                # 'amount_currency': -amount,
                'currency_id': self.company_id.currency_id.id,
                'move_id': am.id,
                'name': _('Move origin: ') + str(move_name)
            },
            {
                'amount_residual': 0,
                'account_id': debit_account.id,
                'balance': 0,
                'credit': 0,
                'debit': 0,
                'ifrs_balance': amount,
                'ifrs_credit': 0,
                'ifrs_debit': amount,
                'ifrs_type': 'ifrs',
                # 'amount_currency': amount,
                'currency_id': self.company_id.currency_id.id,
                'move_id': am.id,
                'name': _('Move origin: ') + str(move_name)
            },
        ]
        return aml_vals

    def create_entry(self, amount, debit_account, credit_account, move_name, partner_id):
        move_obj = self.env['account.move']
        amount = abs(amount)
        if not self.company_id.currency_exchange_journal_id:
            raise ValidationError(
                _('There is not a journal of exchange set in the company.'))
        if not self.company_id.income_currency_exchange_account_id:
            raise ValidationError(
                _('There is not a account of income set in the company.'))
        if not self.company_id.expense_currency_exchange_account_id:
            raise ValidationError(
                _('There is not a account of expense set in the company.'))

        am = move_obj.create({
            'date': self.date_in_moves,
            'journal_id': self.company_id.currency_exchange_journal_id.id,
            'partner_id': partner_id,
            'ifrs_type': 'ifrs',
            'move_type': 'entry',
            'currency_id': self.company_id.currency_id.id,
            'ref': _('Exchange of ') + move_name,
            'exchange_id': self.id
        })
        amls = self.get_move_lines_vals(
            credit_account, debit_account, amount, am, move_name)
        self.env['account.move.line'].create(
            amls
        )
        # .with_context(check_move_validity=False)
        am.action_post()

    def process_entries_for_move_lines(self):
        trm = self.trm_amount
        for move_line in self.move_lines_ids:
            amount = (trm*move_line.amount_residual_currency -
                      move_line.current_exchange_rate*move_line.amount_residual_currency)
            if amount > 0:
                debit_account = move_line.account_id
                credit_account = self.company_id.income_currency_exchange_account_id
            elif amount < 0:
                debit_account = self.company_id.expense_currency_exchange_account_id
                credit_account = move_line.account_id
            else:
                continue
            self.create_entry(amount, debit_account,
                              credit_account, move_line.move_name, move_line.partner_id.id)

    def process_entries_for_account_lines(self):
        trm = self.trm_amount
        for account_bank in self.other_accounts_ids:
            amount = 0
            for move_line in self.move_lines_ids:
                if move_line.account_id == account_bank:
                    amount += (trm*move_line.amount_residual_currency -
                               move_line.current_exchange_rate*move_line.amount_residual_currency)
            if amount > 0:
                debit_account = account_bank
                credit_account = self.company_id.income_currency_exchange_account_id
            elif amount < 0:
                debit_account = self.company_id.expense_currency_exchange_account_id
                credit_account = account_bank
            else:
                continue
            self.create_entry(amount, debit_account,
                              credit_account, move_line.move_name, False)

    def create_difference_in_change(self):
        self.validate_move_date()
        if self.document_type == 'movement':
            self.process_entries_for_move_lines()
        else:
            self.process_entries_for_account_lines()
        self.state = 'done'
        if self.name == '/' or not self.name:
            exch_code = self.env['ir.sequence'].next_by_code(
                'difference.in.change.sequence')
            self.name = exch_code

    def back_to_draft(self):
        self.move_lines_ids = [(5, 0, 0)]
        self.state = 'draft'

    def cancel(self):
        for move in self.exchange_move_ids:
            if move.state == 'posted':
                move.button_draft()
                move.button_cancel()
            elif move.state == 'draft':
                move.button_cancel()
        self.state = 'cancel'

    def revert_movements(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Revert movements'),
            'view_mode': 'form',
            'res_model': 'difference.in.change.revert.wizard',
            'views': [(self.env.ref('difference_in_change_caused.difference_in_change_revert_wizard_form_view').id, 'form')],
            'target': 'new',
            'context': {
                'default_exchange_id': self.id
            },
        }


class DifferenceInChangeRevertWizard(models.TransientModel):
    _name = 'difference.in.change.revert.wizard'
    _description = 'Difference in change revert wizard'

    exchange_id = fields.Many2one(
        'difference.in.change.maker',
        string="Exchange",
        required=True
    )
    revert_date = fields.Date(
        string="Revert date",
        required=True
    )

    def revert_movements(self):
        for move in self.exchange_id.exchange_move_ids:
            reversal_move = self.env['account.move.reversal'].with_context(
                from_exchange_reversal=True
            ).create({
                'date': self.revert_date,
                'move_ids': [(6, 0, [move.id])],
                'journal_id': move.journal_id.id,
                'company_id': move.company_id.id
            })
            reversal_move.reverse_moves()
        self.exchange_id.state = 'reverted'
