# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)



class AccountVoucher(models.Model):
    _name = 'account.voucher'
    _description = 'Accounting Voucher'
    _inherit = ['mail.thread.main.attachment', "mail.activity.mixin","portal.mixin"]
    _order = 'date desc, id desc'

    def _default_journal_id(self):
        domain = [('type', 'in', ('cash', 'bank'))]
        return self.env['account.journal'].search(domain, limit=1)

    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Destination Account',
        readonly=False,
        domain="[('account_type', 'in' ('asset_receivable', 'liability_payable')), ('company_id', '=', company_id)]",
        check_company=True
    )

    amount = fields.Monetary(
        string='Amount',
        tracking=True
    )
    amount_active = fields.Monetary(
        string='Amount Active',
        compute='_compute_amount',
        store=True
    )
    amount_passive = fields.Monetary(
        string='Amount Passive',
        compute='_compute_amount',
        store=True
    )
    amount_reconcile = fields.Monetary(
        string='Amount Reconcile',
        compute='_compute_amount',
        store=True
    )
    amount_voucher = fields.Monetary(
        string='Amount Voucher',
        compute='_compute_amount_voucher',
        store=True
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        readonly=False,
        default=lambda self: self.env.company.currency_id,
        help="The voucher's currency."
    )

    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        required=True,
        copy=False,
    )

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Journal',
        required=True,
        default=_default_journal_id
    )

    line_active_ids = fields.One2many(
        comodel_name='account.voucher.line',
        inverse_name='voucher_active_id',
        string='Active Lines',
        copy=False
    )
    line_passive_ids = fields.One2many(
        comodel_name='account.voucher.line',
        inverse_name='voucher_passive_id',
        string='Passive Lines',
        copy=False
    )
    line_reconcile_ids = fields.One2many(
        comodel_name='account.voucher.line',
        inverse_name='voucher_reconcile_id',
        string='Reconcile Lines',
        copy=False
    )

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Journal Entry',
        readonly=True,
        ondelete='cascade',
        check_company=True,
        copy=False
    )

    name = fields.Char(
        string='Name',
        default=lambda self: _('New'),
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Partner",
        ondelete='restrict',
        domain="['|', ('parent_id','=', False), ('is_company','=', True)]",
        check_company=True,
        tracking=True,
        required=True
    )
    partner_type = fields.Selection(
        selection=[('customer', 'Customer'), ('supplier', 'Supplier')],
        default='customer',
        required=True
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('cancel', 'Cancelled'),
            ('posted', 'Posted'),
        ],
        string='Status',
        readonly=True,
        tracking=True,
        copy=False,
        default='draft'
    )

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        default=lambda self: self.env.user,
    )

    voucher_date = fields.Date(
        string='Voucher Date',
        default=fields.Date.context_today,
        copy=False,
    )
    voucher_reference = fields.Char(
        string="Voucher Reference",
        copy=False,
        help="Reference of the document used to issue this voucher. Eg. check number, file name, etc."
    )
    voucher_type = fields.Selection(
        selection=[
            ('voucher', 'Voucher'),
            ('advance', 'Advance'),
            ('cross', 'Cross'),
        ],
        string='Voucher Type',
        default='voucher',
        required=True,
        tracking=True
    )

    writeoff_amount = fields.Monetary(
        compute='_compute_writeoff',
        string='Difference Amount',
        store=True,
        help="Computed as the difference between the amount stated in the voucher and the sum of allocation on the voucher lines."
    )
    writeoff_comment = fields.Char(
        string='Counterpart Comment',
        default=lambda self: _('Write-Off')
    )
    writeoff_option = fields.Selection(
        selection=[
            ('without_writeoff', 'Keep Open'),
            ('with_writeoff', 'Reconcile Voucher Balance'),
        ],
        string='Voucher Difference',
        required=True,
        default='without_writeoff',
        help="This field helps you to choose what you want to do with the eventual difference between the paid amount and the sum of allocated amounts. You can either choose to keep open this difference on the partner's account, or reconcile it with the voucher(s)"
    )

    order_id = fields.Many2one('sale.order', string="Order")
    confirm_action_post = fields.Boolean('Confirm action post')
    exchange_rate = fields.Float(
        'TRM',
        compute='_compute_exchange_rate',
        store=True, readonly=False)

    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Purchase Order',
        help="Reference to the purchase order associated with this voucher.",
        ondelete="restrict"
    )

    @api.onchange('partner_id', 'voucher_type')
    def _onchange_partner_id(self):
        if self.partner_id:
            values = self._prepare_partner_id()
            self.update(values)

        if self.partner_id and self.voucher_type == 'advance':
            self.account_id = self.partner_id.account_advance_id

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            currency_id = self.journal_id.currency_id or self.company_id.currency_id
            self.update({
                'currency_id': currency_id.id
            })

    @api.onchange('voucher_type')
    def _onchange_voucher_type(self):
        if self.voucher_type == 'advance':
            self.update({
                'line_active_ids': [],
                'line_passive_ids': [],
                'line_reconcile_ids': [],
                'writeoff_option': 'without_writeoff'
            })
        if self.voucher_type == 'cross':
            self.update({
                'amount': 0.0,
                'writeoff_option': 'with_writeoff'
            })

    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env['ir.sequence']
        for vals in vals_list:
            code = 'account.voucher.%s' % vals.get('partner_type')
            vals['name'] = Sequence.next_by_code(code) or _('New')
        return super(AccountVoucher, self).create(vals_list)

    @api.depends('line_active_ids.amount', 'line_passive_ids.amount', 'line_reconcile_ids.amount')
    def _compute_amount(self):
        for voucher in self:
            amount_active = sum(voucher.line_active_ids.mapped('amount'))
            amount_passive = sum(voucher.line_passive_ids.mapped('amount'))
            amount_reconcile = sum(voucher.line_reconcile_ids.mapped('amount'))
            voucher.update({
                'amount_active': amount_active,
                'amount_passive': amount_passive,
                'amount_reconcile': amount_reconcile,
            })

    @api.depends('voucher_type', 'amount', 'amount_passive')
    def _compute_amount_voucher(self):
        for voucher in self:
            if voucher.voucher_type != 'cross':
                amount_voucher = voucher.amount
            else:
                amount_voucher = voucher.amount_passive
            voucher.update({
                'amount_voucher': amount_voucher
            })

    @api.depends('amount', 'amount_active', 'amount_passive')
    def _compute_writeoff(self):
        for voucher in self:
            amount_active = voucher.amount + voucher.amount_active
            amount_passive = voucher.amount_passive
            writeoff_amount = amount_active - amount_passive
            voucher.update({
                'writeoff_amount': writeoff_amount
            })
    
    @api.depends('currency_id', 'date')
    def _compute_exchange_rate(self):
        for voucher in self:
            trm = voucher.currency_id._convert(
                1, voucher.company_id.currency_id, voucher.company_id, voucher.date
            )
            voucher.update({
                'exchange_rate': trm
            })

    def _prepare_partner_id(self):
        self.ensure_one()
        values = {}
        values.update(self._prepare_account_id())
        return values

    def _prepare_account_id(self):
        self.ensure_one()
        partner_id = self.partner_id
        receivable_id = partner_id.property_account_receivable_id
        payable_id = partner_id.property_account_payable_id
        account_id = payable_id if self.partner_type == 'supplier' else receivable_id
        return {'account_id': account_id.id}

    def compute_line_ids(self):
        for voucher in self:
            voucher._compute_line_ids()

    def _compute_line_ids(self):
        self.ensure_one()
        self.line_active_ids.unlink()
        self.line_passive_ids.unlink()
        line_ids = self._prepare_line_ids()
        self.write(line_ids)

    def _prepare_line_ids(self):
        self.ensure_one()
        trm = self.exchange_rate
        value = {
            'line_active_ids': [],
            'line_passive_ids': []
        }

        domain = [
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('partner_id', '=', self.partner_id.id),
            ('account_id.account_type', 'in',
             ('liability_payable', 'asset_receivable'))
        ]
        # if self.voucher_type == 'voucher':
        #     domain.append(('account_id', '=', self.account_id.id))
        if self._context.get('line_ids'):
            domain.append(('id', 'in', self._context.get('line_ids')))
        account_move_lines = self.env['account.move.line'].search(
            domain, order='date_maturity'
        )

        amount_credit = sum((line.credit or 0.0) / trm for line in account_move_lines)
        #     sum(line.currency_id._convert(
        #         line.credit or 0.0, self.currency_id, self.company_id, line.date
        #     ) for line in account_move_lines
        # )
        amount_debit = sum((line.debit or 0.0) / trm for line in account_move_lines)
        #     sum(line.currency_id._convert(
        #         line.debit or 0.0, self.currency_id, self.company_id, line.date
        #     ) for line in account_move_lines
        # )
        amount_active = amount_credit if self.partner_type == 'customer' else amount_debit
        remaining_amount = self.amount + amount_active

        for move_line in account_move_lines:
            if move_line.currency_id and move_line.currency_id.id == self.currency_id.id:
                amount_original = abs(move_line.amount_currency)
                amount_unreconciled = abs(move_line.amount_residual_currency)
            else:
                amount_original = (move_line.debit or move_line.credit) / trm
                #     self.company_currency_id._convert(
                #     move_line.debit or move_line.credit, self.currency_id, self.company_id, self.date
                # )
                amount_unreconciled = abs(move_line.amount_residual) / trm
                #     self.company_currency_id._convert(
                #     abs(move_line.amount_residual), self.currency_id, self.company_id, self.date
                # )

            if not amount_unreconciled:
                continue

            line_debit = amount_unreconciled if move_line.debit else 0.0
            line_credit = amount_unreconciled if move_line.credit else 0.0
            line_active = line_debit if self.partner_type == 'supplier' else line_credit

            amount = min(remaining_amount, amount_unreconciled)

            if line_active > 0:
                amount = amount_unreconciled

            line = {
                'account_id': move_line.account_id.id,
                'amount':  amount if amount >= 0 else amount_unreconciled,
                'amount_original': amount_original,
                'amount_unreconciled': amount_unreconciled,
                'currency_id': self.currency_id.id,
                'line_type': move_line.credit and 'credit' or 'debit',
                'move_line_id': move_line.id,
                'name': move_line.move_id.name,
                'partner_id': self.partner_id.id,
            }

            line_debit = line['amount'] if line['line_type'] == 'debit' else 0.0
            line_credit = line['amount'] if line['line_type'] == 'credit' else 0.0
            line_passive = line_debit if self.partner_type == 'customer' else line_credit

            remaining_amount -= line_passive

            if line['amount_unreconciled'] == line['amount']:
                line['reconcile'] = True

            if line_active > 0:
                value['line_active_ids'].append((0, 0, line))
            else:
                value['line_passive_ids'].append((0, 0, line))
        return value

    def button_line_unlink(self):
        for voucher in self.filtered(lambda v: v.state == 'draft'):
            voucher._button_line_unlink()

    def _button_line_unlink(self):
        self.ensure_one()
        lines = self.line_passive_ids.filtered(lambda l: not l.amount)
        line_passive_ids = [(2, line.id, 0) for line in lines]
        lines = self.line_active_ids.filtered(lambda l: not l.amount)
        line_active_ids = [(2, line.id, 0) for line in lines]
        self.write({
            'line_passive_ids': line_passive_ids,
            'line_active_ids': line_active_ids,
        })

    def button_line_amount(self):
        for voucher in self.filtered(lambda v: v.state == 'draft'):
            voucher._button_line_amount()

    def _button_line_amount(self):
        self.ensure_one()
        lines = self.line_passive_ids + self.line_active_ids
        lines.write({'amount': 0.0, 'reconcile': False})

    def action_post(self):
        for voucher in self:
            voucher._action_post()
            voucher = voucher.with_context(onchange_date_aux=True)
            voucher._action_reconcile()
        return True

    def _action_post(self):
        Move = self.env['account.move']
        self.ensure_one()
        self._check_post()

        move_vals = self._prepare_move_id()
        move_id = Move.with_context(check_move_validity=False).create(move_vals)
        # Balance debit with credit
        debits = sum(x.debit for x in move_id.line_ids)
        credits = sum(x.credit for x in move_id.line_ids)
        if debits != credits:
            if debits > credits:
                difference = debits - credits
                line = move_id.line_ids.filtered(lambda x: x.credit > 0)[0]
                line.with_context(check_move_validity=False).write({'credit': line.credit + difference})
            else:
                difference = credits - debits
                line = move_id.line_ids.filtered(lambda x: x.debit > 0)[0]
                line.with_context(check_move_validity=False).write({'debit': line.debit + difference})
        move_id.action_post()
        self.write({
            'move_id': move_id,
            'state': 'posted',
        })

    def _check_post(self):
        self.ensure_one()

        if self.move_id:
            raise ValidationError(
                _('The voucher already has an accounting entry.')
            )

        if self.writeoff_amount and self.writeoff_option != 'without_writeoff':
            if self.writeoff_amount - self.amount_reconcile != 0.0:
                if self.voucher_type != 'cross':
                    raise ValidationError(
                        _('Cannot confirm a voucher with differences.'))
                else:
                    self.write(self._prepare_reconcile_id())
        return True

    def _action_reconcile(self):
        self.ensure_one()
        if not self.move_id:
            return False
        for line in self.move_id.line_ids.filtered(lambda l: l.voucher_line_id):
            (line | line.voucher_line_id).with_context(
                move_reverse_cancel='cancel'
            ).reconcile()
        if self.env.company.voucher_in_payment_state:
            if not self.check_account_in_payment_state():
                for line in self.move_id.line_ids.filtered(lambda l: l.voucher_line_id):
                    if line.voucher_line_id.move_id.payment_state == 'paid' and line.account_id.account_type == 'asset_receivable':
                        line.voucher_line_id.move_id.payment_state = 'in_payment'

        if self.env.company.use_transient_account:
            for line in self.move_id.line_ids.filtered(lambda l: l.voucher_line_id):
                if line.voucher_line_id.move_id.payment_state == 'paid' and line.account_id.account_type in ('liability_payable', 'asset_receivable'):
                    line.voucher_line_id.move_id.payment_state = 'in_payment'

    def _prepare_move_id(self):
        return {
            'move_type': 'entry',
            'partner_id': self.partner_id.id,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id.id,
            'date': self.date,
            'ref': self.voucher_reference or self.name,
            'voucher_id': self.id,
            'current_exchange_rate': self.exchange_rate,
            'line_ids': self._prepare_move_line_id()
        }

    def get_journal_account(self):
        self.ensure_one()
        account_ref = 'account_journal_payment_debit_account_id' if self.partner_type == 'customer' else 'account_journal_payment_credit_account_id'
        chart_template = self.with_context(allowed_company_ids=self.company_id.root_id.ids).env['account.chart.template']
        outstanding_account = (
            chart_template.ref(account_ref, raise_if_not_found=False)
            or self.company_id.transfer_account_id
        )
        journal = self.journal_id
        default_account_id = journal.default_account_id
        account = default_account_id
        inbound_payment_account_id = journal.inbound_payment_method_line_ids.payment_account_id
        outbound_payment_account_id = journal.outbound_payment_method_line_ids.payment_account_id
        if self.partner_type == 'customer':
            if outstanding_account:
                account = outstanding_account
            return inbound_payment_account_id and inbound_payment_account_id[0] or account
        if self.partner_type == 'supplier':
            if outstanding_account:
                account = outstanding_account
            return outbound_payment_account_id and outbound_payment_account_id[0] or account
        return account

    def check_account_in_payment_state(self):
        self.ensure_one()
        journal = self.journal_id
        default_account_id = journal.default_account_id
        account = default_account_id
        inbound_payment_account_id = journal.inbound_payment_method_line_ids.payment_account_id
        outbound_payment_account_id = journal.outbound_payment_method_line_ids.payment_account_id
        if self.partner_type == 'customer':
            if account == inbound_payment_account_id:
                return True
        if self.partner_type == 'supplier':
            if account == outbound_payment_account_id:
                return True
        return False

    def _prepare_move_line_id(self):
        line_ids = []
        sign = self.partner_type == 'customer' and 1 or -1
        if self.amount:
            amount = self.amount * sign
            amount_currency = amount
            amount = amount_currency * self.exchange_rate
            # amount = self.currency_id._convert(
            #     amount, self.company_currency_id, self.company_id, self.date
            # )
            account = self.get_journal_account()
            line = {
                'name': self.name,
                'debit': amount if amount > 0 else 0.0,
                'credit': -amount if amount < 0 else 0.0,
                'account_id': account.id,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
                'amount_currency': amount_currency,
                'date': self.date,
            }
            line_ids.append((0, 0, line))
        if self.voucher_type != 'advance':
            for line in (self.line_passive_ids | self.line_active_ids).filtered(lambda l: l.amount):
                debit = line.move_line_id.credit and line.amount or 0.0
                credit = line.move_line_id.debit and line.amount or 0.0
                amount_currency = debit - credit
                debit = debit * self.exchange_rate
                # self.currency_id._convert(
                #     debit, self.company_currency_id, self.company_id, self.date
                # )
                credit = credit * self.exchange_rate
                # self.currency_id._convert(
                #     credit, self.company_currency_id, self.company_id, self.date
                # )
                line_vals = {
                    'name': '%s - %s' % (self.name, line.move_line_id.move_id.name),
                    'debit': debit,
                    'credit': credit,
                    'account_id': line.move_line_id.account_id.id,
                    'partner_id': self.partner_id.id,
                    'currency_id': line.currency_id.id,
                    'amount_currency': amount_currency,
                    'date': self.date,
                    'voucher_line_id': line.move_line_id.id,
                }
                line_ids.append((0, 0, line_vals))
        if self.writeoff_amount:
            writeoff_amount = self.writeoff_amount * sign * -1
            if self.writeoff_option == 'without_writeoff':
                amount_currency = writeoff_amount
                writeoff_amount = writeoff_amount * self.exchange_rate
                # self.currency_id._convert(
                #     writeoff_amount, self.company_currency_id, self.company_id, self.date
                # )
                line = {
                    'name': self.name or _('Write-Off'),
                    'debit': writeoff_amount if writeoff_amount > 0 else 0.0,
                    'credit': -writeoff_amount if writeoff_amount < 0 else 0.0,
                    'account_id': self.account_id.id,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                    'amount_currency': amount_currency,
                    'date': self.date,
                }
                line_ids.append((0, 0, line))
            else:
                for line in self.line_reconcile_ids.filtered(lambda l: l.amount):
                    amount = line.amount * sign * -1
                    amount_currency = amount
                    amount = amount * self.exchange_rate
                    # self.currency_id._convert(
                    #     amount, self.company_currency_id, self.company_id, self.date
                    # )
                    lined = {
                        'name': line.comment or _('Write-Off'),
                        'debit': amount if amount > 0 else 0.0,
                        'credit': -amount if amount < 0 else 0.0,
                        'account_id': line.account_id.id,
                        'partner_id': line.partner_id and line.partner_id.id or self.partner_id.id,
                        'currency_id': self.currency_id.id,
                        'amount_currency': amount_currency,
                        'date': self.date,
                        # 'analytic_account_id': line.analytic_id.id,
                        # 'analytic_tag_ids': [(6, id, line.analytic_tag_ids.ids)]
                    }
                    if line.analytic_distribution:
                        lined['analytic_distribution'] = line.analytic_distribution
                    line_ids.append((0, 0, lined))
        return line_ids

    def _prepare_reconcile_id(self):
        sign = self.partner_type == 'customer' and 1 or -1
        accounts = self.journal_id._prepare_voucher_data()
        amount = self.writeoff_amount * sign
        account_id = accounts.get(
            'account_debit') if amount > 0 else accounts.get('account_credit')
        if not account_id:
            raise ValidationError(
                _('No hay cuentas de Recibos de gastos y/o comprobantes de gastos registrados en el diario %s.',
                  self.journal_id.name))

        value = {
            'account_id': account_id.id,
            'amount':  amount,
            'currency_id': self.currency_id.id,
            'name': self.name,
            'partner_id': self.partner_id.id,
        }
        return {
            'line_reconcile_ids': [(0, 0, value)]
        }

    def action_draft(self):
        self.write({'state': 'draft', 'move_id': False})
        return True

    def action_cancel(self):
        for voucher in self.filtered(lambda v: v.move_id):
            voucher.move_id.button_draft()
            voucher.move_id.button_cancel()
        self.write({'state': 'cancel'})
        return True

    def action_voucher_send(self):
        '''
        This function opens a window to compose an email, with the voucher template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        template_id = False
        if self.partner_type == 'customer':
            template_id = ir_model_data._xmlid_lookup(
                'account_voucher.voucher_customer_email_template')[1]
        elif self.partner_type == 'supplier':
            template_id = ir_model_data._xmlid_lookup(
                'account_voucher.voucher_supplier_email_template')[1]

        try:
            compose_form_id = ir_model_data._xmlid_lookup(
                'mail.email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict(self.env.context or {})
        ctx.update({
            'default_model': 'account.voucher',
            'active_model': 'account.voucher',
            'active_id': self.ids[0],
            'default_res_ids': self.ids,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            # 'custom_layout': "mail.mail_notification_paynow",
            'force_email': True,
            # 'mark_rfq_as_sent': True,
        })

        lang = self.env.context.get('lang')
        if {'default_template_id', 'default_model', 'default_res_id'} <= ctx.keys():
            template = self.env['mail.template'].browse(
                ctx['default_template_id'])
            if template and template.lang:
                lang = template._render_lang([ctx['default_res_id']])[
                    ctx['default_res_id']]

        self = self.with_context(lang=lang)
        # if self.state in ['draft', 'sent']:
        #     ctx['model_description'] = _('Request for Quotation')
        # else:
        #     ctx['model_description'] = _('Purchase Order')

        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def action_send_mass_emails(self):
        log_error_obj = self.env['voucher.mail.error']
        error_action = self.env.ref(
            'account_voucher.voucher_mail_error_action')
        # 'account_voucher.voucher_mail_error_form')
        template_sup_id = self.env.ref(
            'account_voucher.voucher_supplier_email_template')
        template_cus_id = self.env.ref(
            'account_voucher.voucher_customer_email_template')
        mail_ok = 0
        mail_error = 0
        doc_error = []
        log_ids = []
        links = []
        for record in self:
            try:
                template_id = False
                if record.partner_type == 'customer':
                    template_id = template_cus_id
                elif record.partner_type == 'supplier':
                    template_id = template_sup_id
                else:

                    _logger.info('Pago sin tipo de tercero %s' % record)
                if template_id:
                    # if mail_ok == 1:
                    #     a = 1/0
                    mail = template_id.send_mail(record.id)
                    mail_ok += 1
                    _logger.info('++++++++++++ EMAIL: %s' % mail)
            except Exception as error:
                mail_error += 1
                doc_error.append('%s (%s)' % (record.name, record.id))
                log_error_id = log_error_obj.create({
                    'name': record.name,
                    'voucher_id': record.id,
                    'error_txt': str(error)
                })
                log_ids.append(log_error_id.id)
        if mail_ok == len(self):
            title = _('ENVÍO EXITOSO')
            type_msg = 'success'
            msg = _('Se enviaron %s correos', mail_ok)
        elif mail_error == len(self):
            title = _('PELIGRO')
            type_msg = 'danger'
            msg = _('Ocurrió un error en %s documentos', mail_error)
        else:
            title = _('ADVERTENCIA')
            type_msg = 'warning'
            msg = _('{ok} correos correctos.\n'
                    '{error} correos errados.\n'
                    'Documentos errados: {doc_error}'.format(
                        ok=mail_ok,
                        error=mail_error,
                        doc_error=', '.join(doc_error)
                    ))
        if log_ids:
            error_action.domain = [('id', 'in', log_ids)]
            links.append({
                'label': _('Ver errores'),
                'url': f"#action={error_action.id}&model=voucher.mail.error",
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': msg + ' %s'*len(links),
                'type': type_msg,
                'links': links,
                'sticky': True,
                'messageIsHtml': True
            }
        }


class AccountVoucherLine(models.Model):
    _name = 'account.voucher.line'
    _inherit = 'analytic.mixin'
    _description = 'Voucher Lines'

    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
        required=True
    )

    amount = fields.Monetary(string='Amount')
    amount_original = fields.Monetary(string='Original Amount')
    amount_unreconciled = fields.Monetary(string='Open Balance')
    amount_untax = fields.Monetary(string='Untax Amount')

    # analytic_id = fields.Many2one(
    #     comodel_name='account.analytic.account',
    #     string='Analytic Account',
    # )
    # analytic_tag_ids = fields.Many2many(
    #     comodel_name='account.analytic.tag',
    #     string='Analytic Tags'
    # )

    comment = fields.Char(
        string='Counterpart Comment',
        default=lambda self:_('Write-Off')
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency'
    )

    date_original = fields.Date(related='move_line_id.date')
    date_due = fields.Date(related='move_line_id.date_maturity')

    line_type = fields.Selection(
        selection=[('debit', 'Debit'), ('credit', 'Credit')],
        string='Debit / Credit'
    )

    move_line_id = fields.Many2one(
        comodel_name='account.move.line',
        string='Journal Item',
        copy=False
    )

    name = fields.Char(string='Description')

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner Lines'
    )

    reconcile = fields.Boolean(
        string='Full Reconcile',
        default=False
    )

    voucher_active_id = fields.Many2one(
        comodel_name='account.voucher',
        string='Active',
        ondelete='cascade'
    )
    voucher_passive_id = fields.Many2one(
        comodel_name='account.voucher',
        string='Passive',
        ondelete='cascade'
    )
    voucher_reconcile_id = fields.Many2one(
        comodel_name='account.voucher',
        string='Reconcile',
        ondelete='cascade'
    )

    @api.onchange('reconcile')
    def _onchange_reconcile(self):
        if self.reconcile:
            self.update({'amount': self.amount_unreconciled})

    @api.onchange('amount')
    def _onchange_amount(self):
        if self.amount:
            self.update({'reconcile': self.amount == self.amount_unreconciled})

    @api.onchange('move_line_id')
    def _onchange_move_line_id(self):
        if self.move_line_id:
            self.update({
                'account_id': self.move_line_id.account_id.id,
                'line_type': self.move_line_id.credit and 'credit' or 'debit',
            })

    @api.onchange('voucher_reconcile_id')
    def _onchange_partner(self):
        if self.voucher_reconcile_id:
            self.update({'partner_id': self.voucher_reconcile_id.partner_id})



class AccountVoucherAdvance(models.Model):
    _name = 'account.voucher.advance'
    _description = 'Voucher advance'

    name = fields.Char()
    account_voucher_id = fields.Many2one('account.voucher', 'Cuenta anticipo')
    order_id = fields.Many2one('sale.order')
