from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta

class HrLoanPaymentWizard(models.Model):
    _name = 'hr.loan.payment.wizard'
    _description = 'Abonar Préstamo'

    loan_id = fields.Many2one(comodel_name='hr.loan', string="Préstamo")
    total_payment = fields.Boolean(string='Pago Total', default=False)
    by_payroll = fields.Boolean(string='Por Nómina?', default=False)
    discount_amount = fields.Float(string="Monto del Descuento")
    quotas = fields.Integer(string='Cuotas restantes')

    @api.onchange('total_payment')
    def _total_payment(self):
        if self.total_payment:
            self.discount_amount = self.loan_id.paid_balance

    def apply_discount(self):
        loan = self.loan_id

        if self.total_payment and self.discount_amount != self.loan_id.paid_balance:
            raise UserError("El monto debe ser igual a total pendiente.")
             
        if self.discount_amount > loan.paid_balance:
            raise UserError("El monto no puede ser mayor al saldo pendiente del préstamo.")

        # Obtener ultimo pago realizado.
        novelty_id = loan.novelty_ids.filtered(lambda nv: nv.novelty_type_id == loan.novelty_type_loan_id)
        paid_installments = [n for n in novelty_id.novelty_line_ids if n.state == 'paid']
        unpaid_installments = loan.novelty_ids.filtered(lambda n: n.state != 'paid')
        for novelty in unpaid_installments:
            novelty_lines = novelty.novelty_line_ids.filtered(lambda n: n.state != 'paid')
            for novelty_line in novelty_lines:
                novelty_line.sudo().unlink()

        contract_schedule_pay = loan.contract_id.schedule_pay
        # Esta fecha debe ser la del ultimo pago
        # Sino existe, se toma la Fecha Inicio date_start
        if (paid_installments):
            paid = paid_installments[-1]
            date_start = paid.period_id.start
            date_start = loan.increase_period_date(date_start, contract_schedule_pay)
        else:
            date_start = loan.date_start

        total_assigned = 0
        period = self.env['hr.period'].sudo().search([
            ('start', '<=', date_start),
            ('end', '>=', date_start),
            ('type_period', '=', loan.contract_id.schedule_pay),
            ('company_id', '=', loan.company_id.id),
            ('active', '=', True)
        ], limit=1)
        if self.by_payroll:
            novelty = loan.novelty_ids.filtered(lambda n: n.state != 'paid' and n.novelty_type_id.id == loan.novelty_type_loan_id.id)
            vals = {
                'state': 'validated',
                'contract_id': loan.contract_id.id,
                'novelty_id': novelty.id,
                'period_id': period.id,
                'amount': self.discount_amount,
            }
            self.env['hr.novelty.line'].sudo().create(vals)
        else: 
            partner_id = loan.employee_id.partner_id.id
            voucher_obj = self.env['account.voucher']
            invoice = loan.account_loan_id.account_move_id
            if (not invoice):
                raise ValidationError("No se puede realizar la operación, debe haber un asiento de Desembolso asociado.")
            voucher = voucher_obj.create({
                'partner_id': partner_id,
                'amount': self.discount_amount,
                'journal_id': loan.journal_id.id,
                'date': fields.Date.today(),
                'voucher_reference': invoice.name, 
            })
            voucher.sudo().write({'name':'PAGO PRÉSTAMO ' + loan.name})
            lines = voucher._prepare_line_ids()
            
            filtered_line_passive_ids = [
                line for line in lines['line_passive_ids']
                if line[2]['move_line_id'] in invoice.invoice_line_ids.ids
            ]
            for line in filtered_line_passive_ids:
                line[2]['amount'] = self.discount_amount
                line[2]['reconcile'] = False

            voucher.line_passive_ids = [(0, 0, line[2]) for line in filtered_line_passive_ids]

            loan.payment = voucher.id
            voucher.sudo().action_post()

        total = loan.paid_balance - self.discount_amount

        if loan.with_interest:
            novelty2 = loan.novelty_ids.filtered(lambda n: n.state != 'paid' and n.novelty_type_id.id == loan.novelty_interest_loan_id.id)
            vals2 = {
                'state': 'validated',
                'contract_id': loan.contract_id.id,
                'novelty_id': novelty2.id,
                'period_id': period.id,
                'amount': novelty2.amount,
            }
            self.env['hr.novelty.line'].sudo().create(vals2)
        
        if (not self.total_payment and self.quotas > 0):
            quota_value = int(round(total  / self.quotas, 0))

            for i in range(self.quotas):
                novelty = loan.novelty_ids.filtered(lambda n: n.state != 'paid' and n.novelty_type_id.id == loan.novelty_type_loan_id.id)
                # La siguiente fecha del periodo se incrementara según
                # El tipo de pago en el contrato.
                date_start = loan.increase_period_date(date_start, contract_schedule_pay)      
                period = self.env['hr.period'].sudo().search([
                    ('start', '<=', date_start),
                    ('end', '>=', date_start),
                    ('type_period', '=', loan.contract_id.schedule_pay),
                    ('company_id', '=', loan.company_id.id),
                    ('active', '=', True)
                ], limit=1)
                vals = {
                    'state': 'validated',
                    'contract_id': loan.contract_id.id,
                    'novelty_id': novelty.id,
                    'period_id': period.id,
                    'amount': quota_value,
                }
                self.env['hr.novelty.line'].sudo().create(vals)

                if loan.with_interest:
                    novelty2 = loan.novelty_ids.filtered(lambda n: n.state != 'paid' and n.novelty_type_id.id == loan.novelty_interest_loan_id.id)
                    vals2 = {
                        'state': 'validated',
                        'contract_id': loan.contract_id.id,
                        'novelty_id': novelty2.id,
                        'period_id': period.id,
                        'amount': novelty2.amount,
                    }
                    self.env['hr.novelty.line'].sudo().create(vals2)

            return {
                    'type': 'ir.actions.act_window',
                    'name': 'Préstamo',
                    'res_model': 'hr.loan',
                    'view_mode': 'form',
                    'res_id': loan.id,
                    'target': 'current',
                }