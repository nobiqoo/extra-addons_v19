# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

STATE = [
    ('draft', 'Borrador'),
    ('confirm', 'Confirmada'),
    ('disbursed', 'Desembolsado'),
    ('cancel', 'Cancelado'),
    ('paid', 'Pagada')
]

class AccountLoan(models.Model):
    _name = 'account.loans'
    _description = 'Préstamos A Empleados'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'name'

    name = fields.Char(string="Referencia del Préstamo", required=True, copy=False, default=lambda self: 'Nuevo')
    loan_amount = fields.Monetary(string="Monto del Préstamo", required=True)
    loan_date = fields.Date(string="Fecha del Préstamo", default=fields.Date.context_today, required=True)
    repayment_term = fields.Integer(string="Plazo de Pago (meses)", required=True)
    installment_amount = fields.Monetary(string="Monto de la Cuota", compute='_compute_installment_amount')
    currency_id = fields.Many2one(
        comodel_name='res.currency', string="Moneda", default=lambda self: self.env.company.currency_id)
    state = fields.Selection(string='Estado', selection=STATE, default='draft')
    account_move_id = fields.Many2one(
        comodel_name='account.move', string="Asiento Contable", readonly=True)
    with_interest = fields.Boolean(string='Con Intereses')
    value_interest = fields.Float(string='Interes Mensual', readonly=True)
    journal_id = fields.Many2one(
        comodel_name='account.journal', string="Diario", required=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner', string="Empleado", required=True)
    balance_due = fields.Monetary(string="Balance Due")
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'seq.account.loans') or ''
        return super(AccountLoan, self).create(vals_list)
    
    @api.depends('loan_amount', 'repayment_term', 'value_interest')
    def _compute_installment_amount(self):
        for loan in self:
            if loan.repayment_term > 0 and loan.repayment_term != 0:
                interest_total  = self.loan_amount * self.value_interest * self.repayment_term if self.with_interest else 0
                total_with_interest = self.loan_amount + interest_total
                loan.balance_due = total_with_interest
                quota_value = round(total_with_interest  / self.repayment_term, 0)
                loan.installment_amount = quota_value
            elif loan.value_interest > 0:
                loan.installment_amount = loan.loan_amount / loan.repayment_term
            else:
                loan.installment_amount = 0.0

    def to_cancel(self):
        for record in self:
            if record.state != 'paid':
                record.state = 'cancel'
                record.account_move_id.sudo().button_cancel()

    def to_draft(self):
        for record in self:
            if record.state != 'paid':
                record.state = 'draft'

    def to_confirm(self):
        for record in self:
            if record.loan_amount <= 0:
                raise UserError('El valor es menor o igual que 0')
            if record.with_interest:
                if record.value_interest <= 0:
                    raise UserError('El valor de interes es menor o igual que 0')
            if record.state == 'draft':
                record.state = 'confirm'

    def to_disbursed(self):
        account_journal = False
        for record in self:
            for account in record.journal_id.outbound_payment_method_line_ids:
                account_journal = account.payment_account_id.id
                break
            if not account_journal:
                if record.journal_id.suspense_account_id:
                    account_journal = record.journal_id.suspense_account_id.id
                else:
                    raise UserError('El diario no tiene cuentas de pagos registradas.')
            settings = self.env['res.config.settings'].search([('company_id', '=', self.company_id.id)], limit=1)
            vals = {
                'ref':record.name,
                'date':record.loan_date,
                'journal_id':record.journal_id.id,
                'way_to_pay':'credit',
                'line_ids': [
                    (0, 0, {
                        'account_id': settings.advance_account_loan_id.id,
                        'partner_id': record.partner_id.id,
                        'debit': record.loan_amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': account_journal,
                        'partner_id': record.partner_id.id,
                        'debit': 0.0,
                        'credit': record.loan_amount, 
                    })]
            }
            account_move_id = record.env['account.move'].create(vals)
            record.account_move_id = account_move_id
            account_move_id.sudo().action_post()
            if record.state == 'confirm':
                record.state = 'disbursed'

    def to_paid(self):
        for record in self:
            if record.state == 'disbursed':
                record.state = 'paid'
