# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class HrExpenseBaseline(models.Model):
    _name = 'hr.expense.advance'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'HR Expense Advance'

    name = fields.Char(
        required=True,
        copy=False,
        default='New'
    )

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        required=True,
    )

    director_id = fields.Many2one(
        comodel_name='hr.employee',
        related='employee_id.coach_id',
        readonly=True,
        copy=False
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    amount = fields.Float()

    local_amount = fields.Float(
        compute='_compute_local_amount'
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company
    )

    date = fields.Date(default=lambda self: fields.Date.context_today(self))

    request_date = fields.Date(
        string='Request Date',
        default=lambda self: fields.Date.context_today(self)
    )

    approval_date = fields.Date(string='Approval Date')

    due_date = fields.Date(
        string='Due Date',
        compute='_compute_due_date',
        store=True
    )

    description = fields.Text()

    journal_id = fields.Many2one('account.journal', copy=False)

    date_accounting = fields.Date(string='Date Accounting', copy=False)

    voucher_out = fields.Many2one(
        comodel_name='account.move',
        string='Voucher Out',
        readonly=True,
        copy=False
    )

    account_payable = fields.Many2one(
        comodel_name='account.account',
        string='Account Payable',
        readonly=True
    )
    account_receivable = fields.Many2one(
        comodel_name='account.account',
        string='Account Receivable',
        readonly=True
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('pending_approval', 'Pending Approval'),
            ('generate_advance', 'Generate Advance'),
            ('pending_legalization', 'Pending Legalization'),
            ('approved', 'Approved'),
            ('expired', 'Expired'),
        ],
        default='draft',
        string='State',
        tracking=True
    )
    expense_ids = fields.One2many(
        'hr.expense', 'advance_id', string='Expenses')

    paid_expense_ids = fields.Many2many(
        'hr.expense',
        string='Related sheets',
        compute='_compute_paid_expense_ids',
        readonly=True
    )
    legalization_amount = fields.Monetary(string='Total Legalizado por Gastos', currency_field='currency_id')
    payment_amount = fields.Monetary(string='Total Pagado Manual', currency_field='currency_id')

    @api.depends('expense_ids')
    def _compute_paid_expense_ids(self):
        for advance in self:
            advance.paid_expense_ids = advance.expense_ids

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hr.expense.advance') or 'New'

            advance_account_employee = self.env.company.advance_account_employee
            if advance_account_employee:
                vals['account_receivable'] = advance_account_employee.id
            else:
                raise UserError(
                    _('Configure the Advance Account for Employees in the settings')
                )

        return super(HrExpenseBaseline, self).create(vals_list)

    @api.depends('request_date')
    def _compute_due_date(self):
        days_for_due = int(
            self.env['ir.config_parameter']
            .sudo()
            .get_param('hr_expense_baseline.days_for_due')
        )
        if not days_for_due:
            raise UserError(
                _('Please configure the Days for Due Date from Settings.'))

        for record in self:
            if record.request_date:
                record.due_date = record.request_date + \
                    timedelta(days=days_for_due)
            else:
                record.due_date = None

    @api.depends('amount', 'currency_id')
    def _compute_local_amount(self):
        for record in self:
            record.local_amount = record.currency_id._convert(
                record.amount,
                record.company_id.currency_id,
                record.company_id,
                fields.Date.today(),
            )

    @api.constrains('description', 'state')
    def _check_description_content(self):
        for record in self:
            if record.state == 'draft' and (not record.description):
                raise ValidationError(
                    _('The description is required for draft state.'))

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            if not self.journal_id.default_account_id:
                raise UserError(
                    _('The journal does not have a default account'))
            else:
                self.account_payable = self.journal_id.default_account_id

    def write(self, vals):
        if 'journal_id' in vals:
            journal = self.env['account.journal'].browse(vals['journal_id'])
            if journal:
                vals['account_payable'] = journal.default_account_id.id
        return super(HrExpenseBaseline, self).write(vals)

    def action_send(self):
        template = self.env.ref(
            'hr_expense_baseline.mail_template_advance_notification')

        for advance in self:
            advance.write({
                'state': 'pending_approval'
            })
            template.send_mail(advance.id, force_send=True)

    def action_approved(self):
        for advance in self:
            if (
                self.env.user != advance.employee_id.coach_id
                and self.env.user not in advance.employee_id.approvers_ids
            ):
                raise UserError(
                    _('You are not allowed to approve this advance.')
                )
            advance.state = 'generate_advance'
            advance.approval_date = fields.Date.context_today(self)

    def action_decline(self):
        for advance in self:
            if (
                self.env.user != advance.employee_id.coach_id
                and self.env.user not in advance.employee_id.approvers_ids
            ):
                raise UserError(
                    _('You are not allowed to decline this advance.')
                )
            advance.state = 'expired'

    def action_generate_advance(self):
        AccountMove = self.env['account.move']

        for advance in self:
            debit_line_vals = {
                'name': _('Advance: %s') % advance.name,
                'partner_id': self.employee_id.partner_id.id,
                'account_id': advance.account_receivable.id,
                'debit': advance.amount,
                'credit': 0.0,
            }

            credit_line_vals = {
                'name': _('Advance: %s') % advance.name,
                'partner_id': self.employee_id.partner_id.id,
                'account_id': advance.account_payable.id,
                'debit': 0.0,
                'credit': advance.amount,
            }

            move_vals = {
                'ref': advance.name,
                'journal_id': advance.journal_id.id,
                'date': advance.date_accounting,
                'currency_id': advance.currency_id.id,
                'line_ids': [(0, 0, debit_line_vals), (0, 0, credit_line_vals)],
            }

            if advance.voucher_out:
                move = advance.voucher_out

                if move.state == 'posted':
                    move.button_draft()

                move.line_ids.unlink()
                move.write(move_vals)
            else:
                move = AccountMove.create(move_vals)
                advance.voucher_out = move.id

            move.action_post()

            advance.state = 'pending_legalization'

    def action_draft(self):
        for advance in self:
            advance.state = 'draft'

    def check_and_update_expired_advances(self):
        today = fields.Date.context_today(self)

        expired_advances = self.search(
            [
                ('state', 'in', ['draft', 'pending_approval',
                 'generate_advance', 'pending_legalization']),
                ('due_date', '<', today),
            ]
        )

        expired_advances.write({'state': 'expired'})
    
    def recompute_legalization_state(self):
        for advance in self:
            paid_expenses = advance.expense_ids.filtered(
                lambda exp: exp.state in ('paid', 'done')
                or exp.account_move_id.payment_state == 'paid'
            )
            amount_expenses = sum(paid_expenses.mapped('total_amount'))

            legacy_sheet_lines = self.env['hr.expense'].search([
                ('advance_id', '=', advance.id),
                ('state', 'in', ['approve', 'post', 'done'])
            ])
            if 'expense_line_ids' in legacy_sheet_lines._fields:
                expense_lines = legacy_sheet_lines.expense_line_ids.filtered(
                    lambda l: l.advance_id.id == advance.id
                )
                amount_expenses += sum(expense_lines.mapped('total_amount'))

            reconciled_lines = self.env['account.move.line']
            if advance.voucher_out:
                for line in advance.voucher_out.line_ids.filtered(lambda l: l.reconciled):
                    reconciled_lines += line.full_reconcile_id.reconciled_line_ids.filtered(
                        lambda l: l.id != line.id and l.account_id == advance.account_receivable
                    )

            excluded_move_ids = []
            if 'account_move_ids' in advance.expense_ids._fields:
                excluded_move_ids += advance.expense_ids.mapped('account_move_ids').ids
            if 'account_move_id' in advance.expense_ids._fields:
                excluded_move_ids += advance.expense_ids.mapped('account_move_id').ids
            reconciled_lines = reconciled_lines.filtered(lambda l: l.move_id.id not in excluded_move_ids)

            amount_reconciled = sum(abs(l.balance) for l in reconciled_lines)
            advance.legalization_amount = amount_expenses
            advance.payment_amount = amount_reconciled

            amount_to_legalize = advance.local_amount or advance.amount
            if (amount_expenses + amount_reconciled) >= amount_to_legalize:
                advance.state = 'approved'
            else:
                advance.state = 'pending_legalization'