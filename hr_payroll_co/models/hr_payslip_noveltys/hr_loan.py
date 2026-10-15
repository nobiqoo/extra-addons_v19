# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

class HrLoan(models.Model):
    _name = 'hr.loan'
    _inherit = 'model.basic.payslip.novelty'
    _description = 'Préstamos'
    _order = 'name'

    quotas = fields.Integer(string='Cuotas')
    novelty_ids = fields.One2many(
        comodel_name='hr.novelty', inverse_name='loan_id', readonly=True, string='Novedades')
    with_interest = fields.Boolean(string='Con Intereses')
    with_disbursement = fields.Boolean(string='¿Quiere crear un asiento contable de desembolso?')
    value_interest = fields.Float(string='Interes Mensual')
    journal_id = fields.Many2one(
        comodel_name='account.journal', string="Diario", required=True)
    account_loan_id = fields.Many2one(
        comodel_name='account.loans', string="Desembolso")
    paid_balance = fields.Float(string='Saldo Pendiente', 
                                compute='_compute_paid_balance', store=True)
    paid_total = fields.Float(string='Saldo Pendiente')
    interest_value = fields.Float(string='Interes Mensual Valor')
    remaining_installments = fields.Integer(string='Cuotas Pendientes')
    payment = fields.Many2one(
        comodel_name='account.voucher', string='Pago')
    novelty_type_loan_id = fields.Many2one(
        comodel_name='hr.novelty.type',
        string='Categoría De Préstamo Empleados',
        required=True
    )
    novelty_interest_loan_id = fields.Many2one(
        comodel_name='hr.novelty.type',
        string='Categoría De Interes Préstamo Empleados'
    )
    is_biweekly = fields.Boolean(string='¿Es Nómina Quincenal?', compute='_compute_is_biweekly', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'seq.hr.loan') or ''
        return super(HrLoan, self).create(vals_list)

    def _compute_is_biweekly(self):
        for record in self:
            if record.contract_id.schedule_pay == 'BIWEEKLY' and not record.novelty_type_loan_id.single_biweekly_payment:
                record.is_biweekly = True
            else:
                record.is_biweekly = False

    @api.depends('novelty_ids', 'novelty_ids.state', 'payment','novelty_ids.novelty_line_ids.state')
    def _compute_paid_balance(self):
        for record in self:
            payment = 0
            total_paid = sum(
                novelty_line.amount
                for novelty in record.novelty_ids
                if novelty.novelty_type_id.id == record.novelty_type_loan_id.id
                for novelty_line in novelty.novelty_line_ids
                if novelty_line.state == 'paid'
            )
            if record.payment:
                payment = record.payment.amount
            record.paid_balance = record.amount - total_paid - payment

            if record.paid_balance == 0 and record.state == 'validated':
                record.state = 'paid'
                record.account_loan_id.sudo().to_paid()
                for novelty in record.novelty_ids:
                    if novelty.state != 'paid':
                        novelty.state = 'paid'
            
            record.remaining_installments = sum(
                1
                for novelty in record.novelty_ids
                for novelty_line in novelty.novelty_line_ids
                if novelty.novelty_type_id.id == record.novelty_type_loan_id.id
                if novelty_line.state != 'paid'
            )

            # Actualizar las líneas de intereses
            if record.with_interest and record.novelty_interest_loan_id:
                for novelty in record.novelty_ids.filtered(
                    lambda n: n.novelty_type_id.id == record.novelty_interest_loan_id.id
                ):
                    for novelty_line in novelty.novelty_line_ids:
                        if novelty_line.state != 'paid':
                            if record.paid_balance:
                                # Recalcular el interés basado en el saldo pendiente
                                interest_value = record.paid_balance * record.value_interest
                                novelty_line.amount = interest_value

    def to_validated(self):
        for record in self:
            if record.state != 'confirm':
                continue
            if record.with_interest and not record.novelty_interest_loan_id:
                raise UserError('No tiene categoria para los intereses')
            unpaid_installments = record.novelty_ids.filtered(lambda n: n.state != 'paid')
            for novelty in unpaid_installments:
                novelty.novelty_line_ids.sudo().unlink()
            unpaid_installments.sudo().unlink()
            date_start = record.date_start
            date_end = record.date_start
            currency = record.company_id.currency_id
            interest_total = record.amount * record.value_interest * record.quotas if record.with_interest else 0
            record.interest_value = currency.round(interest_total / record.quotas)
            quota_value = currency.round(record.amount / record.quotas)
            record.paid_total = record.amount
            if record.is_biweekly:
                # Calcula los meses totales
                months = (record.quotas) / 2
                
                if months % 1 == 0.5:  # Verifica si el resultado tiene un decimal .5
                    date_end += relativedelta(months=int(months)) 
                else:
                    date_end += relativedelta(months=(months)) - relativedelta(days=15)
            else:
                if record.contract_id.schedule_pay == 'BIWEEKLY' and record.novelty_type_loan_id.single_biweekly_payment:
                    date_end += relativedelta(months=(record.quotas))
                    if date_start.day < 15 and record.novelty_type_loan_id.biweekly_type == 'FIRST':
                        date_start = date_start.replace(day=16)
                    elif date_start.day > 14 and record.novelty_type_loan_id.biweekly_type == 'SECOND':
                        # Ir al 15 del mes siguiente
                        date_end -= relativedelta(months=1)
                else:
                    date_end += relativedelta(months=(record.quotas-1))
            vals = {
                'state': 'confirm',
                'contract_id': record.contract_id.id,
                'type_novelty': 'RECURRENT',
                'employee_id': record.employee_id.id,
                'approve_date': record.approve_date,
                'date_start': date_start,
                'date_end': date_end,
                'amount': quota_value,
                'novelty_type_id': record.novelty_type_loan_id.id,
                'loan_id': record.id,
            }
            hr_novelty = record.env['hr.novelty'].sudo().create(vals)
            hr_novelty.sudo().to_validated()

            if record.with_interest:
                vals2 = {
                    'state': 'confirm',
                    'contract_id': record.contract_id.id,
                    'type_novelty': 'RECURRENT',
                    'employee_id': record.employee_id.id,
                    'approve_date': record.approve_date,
                    'date_start': date_start,
                    'date_end': date_end,
                    'amount': record.interest_value,
                    'novelty_type_id': record.novelty_interest_loan_id.id,
                    'loan_id': record.id,
                }
                hr_novelty2 = record.env['hr.novelty'].sudo().create(vals2)
                hr_novelty2.sudo().to_validated()
            if record.with_disbursement:
                partner_id = record.employee_id.partner_id.id
                vals_loan = {
                    'name':record.name,
                    'state': 'confirm',
                    'partner_id': partner_id,
                    'loan_amount': record.amount,
                    'repayment_term': record.quotas,
                    'with_interest': record.with_interest,
                    'value_interest': record.value_interest,
                    'journal_id': record.journal_id.id,
                }

                account_loan_id = record.env['account.loans'].create(vals_loan)
                record.account_loan_id = account_loan_id.id
                account_loan_id.to_disbursed()

        return super(HrLoan, self).to_validated()

    def to_cancel(self):
        for record in self:
            for novelty_id in record.novelty_ids:
                for novelty_line in novelty_id.novelty_line_ids:
                    if novelty_line.state == 'paid':
                        raise UserError('No se puede cancela, ya tiene un pago registrado')
                else:
                    novelty_id.sudo().to_cancel()
            record.account_loan_id.sudo().to_cancel()
        return super(HrLoan, self).to_cancel()

    def liquidate_loan(self, period):
        # Filtrar las cuotas no pagadas
        unpaid_installments = self.novelty_ids.filtered(lambda n: n.state != 'paid')
        
        # Eliminar líneas no pagadas de todas las cuotas no pagadas
        unpaid_lines = unpaid_installments.mapped('novelty_line_ids').filtered(lambda n: n.state != 'paid')
        unpaid_lines.sudo().unlink()

        # Obtener la novedad específica
        config = self.env['res.config.settings'].sudo().search([])
        novelty = self.novelty_ids.filtered(lambda n: n.state != 'paid' and n.novelty_type_id.id == self.novelty_type_loan_id.id)

        # Crear la nueva línea de novedad
        if novelty:
            vals = {
                'state': 'validated',
                'contract_id': self.contract_id.id,
                'novelty_id': novelty.id,
                'period_id': period.id,
                'amount': self.paid_balance,
            }
            self.env['hr.novelty.line'].sudo().create(vals)

    def to_draft(self):
        for record in self:
            for novelty_id in record.novelty_ids:
                for novelty_line in novelty_id.novelty_line_ids:
                    if novelty_line.state == 'paid':
                        raise UserError('No se puede pasar a borrador, ya tiene un pago registrado')
                else:
                    novelty_id.sudo().to_cancel()
            if record.account_loan_id.state != 'cancel':
                record.account_loan_id.sudo().to_cancel()
        return super(HrLoan, self).to_draft()
    
    def to_confirm(self):
        for record in self:
            if record.quotas <= 0:
                raise UserError('Las cuotas es menor o igual que 0')
            if record.amount <= 0:
                raise UserError('El valor es menor o igual que 0')
            if record.with_interest:
                if record.value_interest <= 0:
                    raise UserError('El valor de interes es menor o igual que 0')
        return super(HrLoan, self).to_confirm()

    def open_payment_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Abono de Préstamo',
            'res_model': 'hr.loan.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_loan_id': self.id, 
            }
        }
