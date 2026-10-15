# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import clean_context


class HrExpense(models.Model):
    _inherit = "hr.expense"
    
    user_id = fields.Many2one(
    comodel_name='res.users',
    string="Manager",
    compute='_compute_from_employee_id', store=True, readonly=True,
    domain=lambda self: [('groups_id', 'in', self.env.ref('hr_expense.group_hr_expense_team_approver').id)],
    copy=False,
    tracking=True,
    )
    
    partner_id = fields.Many2one("res.partner", string="Partner")

    @api.model
    def _default_expense_journal_id(self):
        """
             The journal is determining the company of the accounting entries generated from expense.
             We need to force journal company and expense sheet company to be the same.
        """
        company_journal_id = self.env.company.expense_journal_id
        if company_journal_id:
            return company_journal_id.id
        default_company_id = self.default_get(['company_id'])['company_id']
        journal = self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(default_company_id),
            ('type', '=', 'purchase'),
        ], limit=1)
        return journal.id

    type = fields.Selection(
        [
            ("advance", "Advance"),
            ("expense_refund", "Expense Refund"),
            ("expense_petty_cash", "Expense Petty Cash"),
        ]
    )

    advance_id = fields.Many2one("hr.expense.advance")

    partner_id = fields.Many2one("res.partner")

    petty_cash_responsible_id = fields.Many2one(
        'res.partner',
        domain="[('petty_cash_opened', '=', True)]"
    )

    petty_cash_fund = fields.Float(compute="_compute_petty_cash_fund")
    expense_journal_id = fields.Many2one(
        'account.journal',
        string='Diario de gastos',
        compute='_compute_expense_journal_id',
        store=True,
        readonly=False,
        check_company=True,
        domain="[('type', '=', 'purchase'), ('company_id', '=', company_id)]",
    )

    related_employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string="Related Employee",
        related='employee_id',
        store=True,
        readonly=True,
    )

    @api.onchange('petty_cash_responsible_id')
    def _onchange_bank_journal_id(self):
        for record in self:
            if record.type == 'expense_petty_cash' and record.petty_cash_responsible_id:
                record.expense_journal_id = record.petty_cash_responsible_id.petty_cash_journal

    @api.depends('company_id')
    def _compute_expense_journal_id(self):
        Journal = self.env['account.journal']
        for expense in self:
            if expense.expense_journal_id and expense.expense_journal_id.company_id == expense.company_id:
                continue
            company = expense.company_id or self.env.company
            journal = company.expense_journal_id
            if not journal:
                journal = Journal.search([
                    *Journal._check_company_domain(company),
                    ('type', '=', 'purchase'),
                ], limit=1)
            expense.expense_journal_id = journal

    @api.onchange('type', 'advance_id')
    def _ocnhange_total_amount(self):
        if self.type == 'advance' and self.advance_id:
            if self.advance_id.expense_ids:
                expense_sum = sum(x.total_amount for x in self.advance_id.expense_ids)
                self.total_amount_currency = self.advance_id.amount - expense_sum
            else:
                self.total_amount_currency = self.advance_id.amount

    @api.depends('petty_cash_responsible_id.petty_cash_journal.fund')
    def _compute_petty_cash_fund(self):
        for record in self:
            if record.petty_cash_responsible_id:
                record.petty_cash_fund = record.petty_cash_responsible_id.petty_cash_journal.fund
            else:
                record.petty_cash_fund = 0.0

    @api.constrains("type", "advance_id")
    def _check_advance_id_for_advance_type(self):
        for record in self:
            if record.type == "advance" and not record.advance_id:
                raise ValidationError(
                    _("You must select an Advance for Expense of type 'Advance'.")
                )

    def _get_account_advance(self):
        return self.advance_id.account_receivable.id

    def _get_account_petty_cash(self):
        return self.petty_cash_responsible_id.petty_cash_journal.account_refund_petty_cash.id

    def _get_account_refund_expense(self):
        refund_expense_account = self.env.company.refund_expense_account
        if refund_expense_account:
            refund_expense_account.id
        else:
            raise UserError(
                _('Configure the Refund expense account in settings/account')
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("type") == "expense_petty_cash":
                partner = self.env['res.partner'].browse(
                    vals.get("petty_cash_responsible_id"))
                if vals.get("total_amount_currency") > partner.petty_cash_journal.fund:
                    raise UserError(
                        _("The total amount of the expense is greater than the fund of the petty cash responsible."))
        return super(HrExpense, self).create(vals_list)
    
    def _prepare_bills_vals(self):
        self.ensure_one()
        sheet_id = self.sheet_id
        values = {
            # force the name to the default value, to avoid an eventual 'default_name' in the context
            # to set it to '' which cause no number to be given to the account.move when posted.
            'name': '/',
            'date': sheet_id.accounting_date or self.date or fields.Date.context_today(self),
            'expense_sheet_id': sheet_id.id,
            'expense_id': self.id,

            'invoice_date': sheet_id.accounting_date or fields.Date.context_today(self),
            'journal_id': self.expense_journal_id.id,
            'ref': '{}: {}'.format(sheet_id.name or _('Legalización'), self.name or _('Gasto')),
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id, #self.employee_id.sudo().address_home_id.commercial_partner_id.id,
            'currency_id': self.currency_id.id,
            'line_ids': [Command.create(expense._prepare_move_lines_vals()) for expense in self],
            'attachment_ids': [
                Command.create(attachment.copy_data({'res_model': 'account.move', 'res_id': False, 'raw': attachment.raw})[0])
                for attachment in self.message_main_attachment_id
            ],
            'company_id': self.company_id.id,
        }
        femod = self.env.ref('base.module_l10n_co_bloodo')
        if femod.state == 'installed':
            if self.expense_journal_id.is_einvoicing:
                values['fe_send_later'] = True
        self._check_and_approve_advance()
        return values
    
    def _prepare_move_lines_vals(self):
        values = super(HrExpense, self)._prepare_move_lines_vals()
        values['partner_id'] = self.partner_id.id
        return values
    
    def _get_default_expense_sheet_values(self):
        res = super(HrExpense, self)._get_default_expense_sheet_values()
        expense_obj = self.env['hr.expense']
        for value in res:
            ids = []
            for line in value.get('expense_line_ids', []):
                ids += line[2]
            expense_ids = expense_obj.search([('id', 'in', ids)])
            if expense_ids:
                value['employee_journal_id'] = expense_ids[-1].expense_journal_id.id
        return res

    def _post_without_wizard(self):
        self._check_can_create_move()
        today = fields.Date.context_today(self)
        employee_expenses = self.filtered(lambda expense: expense.payment_mode == 'own_account')
        grouped_expenses = {}

        for expense in employee_expenses:
            company = expense.company_id
            journal = expense.expense_journal_id or company.expense_journal_id
            if not journal:
                company_domain = self.env['account.journal']._check_company_domain(company)
                journal = self.env['account.journal'].search([
                    *company_domain,
                    ('type', '=', 'purchase'),
                ], limit=1)
            key = (company.id, journal.id)
            if key not in grouped_expenses:
                grouped_expenses[key] = {
                    'company': company,
                    'journal': journal,
                    'expenses': self.env['hr.expense'],
                }
            grouped_expenses[key]['expenses'] |= expense

        for group in grouped_expenses.values():
            company = group['company']
            journal = group['journal']
            expenses = group['expenses'].with_company(company)
            expense_receipt_vals_list = [
                {
                    **new_receipt_vals,
                    'journal_id': journal.id,
                    'invoice_date': today,
                }
                for new_receipt_vals in expenses._prepare_receipts_vals()
            ]
            moves = self.env['account.move'].sudo().create(expense_receipt_vals_list)
            for move in moves:
                move._message_set_main_attachment_id(move.attachment_ids, force=True, filter_xml=False)
            moves.action_post()
    
    def _check_and_approve_advance(self):
        """Marcar el anticipo como aprobado si ya fue legalizado completamente."""
        for expense in self:
            advance = expense.advance_id
            if not advance:
                continue
            total_gastos = sum(exp.total_amount for exp in self.env['hr.expense'].search([('advance_id', '=', advance.id)]))
            if total_gastos >= advance.amount and advance.state != 'approved':
                advance.state = 'approved'
                
    @api.depends('employee_id', 'employee_id.department_id')
    def _compute_from_employee_id(self):
        for sheet in self:
            sheet.department_id = sheet.employee_id.department_id
            sheet.user_id = sheet.employee_id.expense_manager_id or sheet.employee_id.parent_id.user_id


    def set_to_paid(self):
        if self.type == "expense_petty_cash":
            expense_journal = self.petty_cash_responsible_id.petty_cash_journal
            expense_journal.increase_fund(self.total_amount_currency)
        super().set_to_paid()
    
    def _calculate_advance_state(self):
        self.ensure_one()
        sheet_obj = self.env['hr.expense']
        advance_id = self.advance_id
        state = advance_id.state
        sheet_ids = sheet_obj.search([('advance_id','=',advance_id.id),
                                      ('payment_state','!=','not_paid')])
        expense_ids = sheet_ids.expense_line_ids.filtered(
            lambda x: x.advance_id.id == advance_id.id)
        amount_expenses = sum(expense_ids.mapped('total_amount'))
        if amount_expenses >= advance_id.local_amount:
            state = 'approved'
        else:
            state = 'pending_legalization'
        return state

    def _check_can_approve(self):
        super()._check_can_approve()
        if self.env.user not in self.employee_id.approvers_ids:
            raise UserError(
                _("You are not allowed to approve this expense sheet."))
    
    def activity_update(self):
        reports_requiring_feedback = self.env['hr.expense']
        reports_activity_unlink = self.env['hr.expense']
        for expense_report in self:
            if expense_report.state == 'submit':
                expense_report.activity_schedule(
                    'hr_expense.mail_act_expense_approval',
                    user_id=expense_report.sudo()._get_responsible_for_approval().id or self.env.user.id)
            elif expense_report.state == 'approved':
                reports_requiring_feedback |= expense_report
            elif expense_report.state in {'draft', 'cancel'}:
                reports_activity_unlink |= expense_report
        if reports_requiring_feedback:
            reports_requiring_feedback.activity_feedback(['hr_expense.mail_act_expense_approval'])
        if reports_activity_unlink:
            reports_activity_unlink.activity_unlink(['hr_expense.mail_act_expense_approval'])

    def _do_create_moves(self):
        self = self.with_context(clean_context(self.env.context))  # remove default_*
        skip_context = {
            'skip_invoice_sync': True,
            'skip_invoice_line_sync': True,
            'skip_account_move_synchronization': True,
        }
        own_account_sheets = self.filtered(lambda sheet: sheet.payment_mode == 'own_account')
        company_account_sheets = self - own_account_sheets

        moves = self.env['account.move'].create([expense._prepare_bills_vals() for expense in own_account_sheets.expense_line_ids])
        # Set the main attachment on the moves directly to avoid recomputing the
        # `register_as_main_attachment` on the moves which triggers the OCR again
        for move in moves:
            move.message_main_attachment_id = move.attachment_ids[0] if move.attachment_ids else None
        payments = self.env['account.payment'].with_context(**skip_context).create([
            expense._prepare_payments_vals() for expense in company_account_sheets.expense_line_ids
        ])
        moves |= payments.move_id
        moves.action_post()
        self.activity_update()
        return moves


    def action_sheet_move_post(self):
        for sheet in self.filtered(lambda s: s.type == 'expense_petty_cash'):
            if sheet.total_amount > sheet.petty_cash_fund:
                raise UserError(_(
                    "El total del reporte (%s) excede el fondo disponible en la caja menor (%s)."
                ) % (sheet.total_amount, sheet.petty_cash_fund))
    
        self.filtered(lambda sheet: not sheet.account_move_id)._do_create_moves()

        company_sheets = self.filtered(lambda sheet: sheet.payment_mode == 'company_account')
        employee_sheets = self - company_sheets

        employee_sheets.account_move_id.filtered(lambda x: x.state == 'draft').action_post()
        company_sheets.account_move_id.origin_payment_id.action_post()

        for sheet in self:
            if sheet.type == 'expense_petty_cash':
                petty_cash_journal = sheet.petty_cash_responsible_id.petty_cash_journal
                if petty_cash_journal:
                    petty_cash_journal.fund -= sheet.total_amount
                continue

            if sheet.type != 'advance':
                continue

            move_anticipo = sheet.advance_id.voucher_out
            if not move_anticipo:
                continue

            def _open_receivable_lines():
                return move_anticipo.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                    and not l.full_reconcile_id
                    and abs(l.amount_residual) > 0
                )

            anticipo_restante = sum(abs(l.amount_residual) for l in _open_receivable_lines())

            move_gastos = sheet.account_move_id.filtered(lambda m: m.move_type in ('in_invoice', 'entry'))

            for move_gasto in move_gastos:
                if anticipo_restante <= 0:
                    break

                lines_gasto = move_gasto.line_ids.filtered(
                    lambda l: l.account_id
                    and l.account_id.account_type in ('liability', 'liability_payable')
                    and not l.full_reconcile_id
                    and abs(l.amount_residual) > 0
                )
                if not lines_gasto:
                    continue

                gasto_residual = sum(abs(l.amount_residual) for l in lines_gasto)
                cruce = min(anticipo_restante, gasto_residual)
                if cruce <= 0:
                    continue

                receivable_lines_open = _open_receivable_lines()
                if not receivable_lines_open:
                    break
                receivable_account = receivable_lines_open[0].account_id

                company = self.env.company
                if (not company.expenses_journal_id):
                    raise UserError(_(
                        "Debe configurar un díario para cruce de gastos en la compañía."
                    ))
                else:
                    cross_journal = company.expenses_journal_id.id

                inter_move = self.env['account.move'].create({
                    'move_type': 'entry',
                    'ref': f'Cruzamiento {sheet.name}',
                    'date': move_gasto.date or fields.Date.context_today(sheet),
                    'journal_id': cross_journal,
                    'line_ids': [
                        (0, 0, {
                            'name': 'Cruce anticipo',
                            'account_id': receivable_account.id,
                            'credit': cruce,
                            'debit': 0.0,
                            'partner_id': sheet.employee_id.address_home_id.id,
                        }),
                        (0, 0, {
                            'name': 'Cruce gasto',
                            'account_id': lines_gasto[0].account_id.id,
                            'debit': cruce,
                            'credit': 0.0,
                            'partner_id': sheet.employee_id.address_home_id.id,
                        }),
                    ]
                })
                inter_move.action_post()

                anticipo_open = _open_receivable_lines()
                inter_anticipo_line = inter_move.line_ids.filtered(
                    lambda l: l.account_id.id == receivable_account.id and l.credit > 0
                )
                if anticipo_open and inter_anticipo_line:
                    (anticipo_open + inter_anticipo_line).reconcile()

                payable_open = move_gasto.line_ids.filtered(
                    lambda l: l.account_id
                    and l.account_id.account_type in ('liability', 'liability_payable')
                    and not l.full_reconcile_id
                    and abs(l.amount_residual) > 0
                )
                inter_gasto_line = inter_move.line_ids.filtered(
                    lambda l: l.account_id.id == lines_gasto[0].account_id.id and l.debit > 0
                )
                if payable_open and inter_gasto_line:
                    (payable_open + inter_gasto_line).reconcile()

                anticipo_restante -= cruce

            move_gastos._compute_payment_state()
            if all(m.state == 'paid' for m in move_gastos):
                sheet.state = 'posted'

            if sheet.advance_id and sheet.advance_id.state not in ('approved', 'expired'):
                sheet.advance_id.state = sheet._calculate_advance_state()

        return True

    def _do_approve(self, check=True):
        if check:
            self._check_can_approve()
        sheets_to_approve = self.filtered(lambda s: s.state in {'submitted', 'draft'})
        for sheet in sheets_to_approve:
            sheet.write({
                'approval_state': 'approved',
                'user_id': sheet. user_id.id or self.env.user.id,
                'approval_date': fields.Date.context_today(sheet),
            })
        self.activity_update()


class HrExpensePostWizard(models.TransientModel):
    _inherit = 'hr.expense.post.wizard'

    @api.model
    def _default_journal_id(self):
        expenses = self.env['hr.expense'].browse(self.env.context.get('active_ids', []))
        expense_journal = expenses.expense_journal_id
        if len(expense_journal) == 1:
            return expense_journal.id
        return super()._default_journal_id()
