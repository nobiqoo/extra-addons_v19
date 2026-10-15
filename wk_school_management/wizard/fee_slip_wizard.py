# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
import logging
import math
from odoo import models, fields, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class FeeSlipGenerateWizard(models.TransientModel):
    _name = 'wk.fee.generate.wizard'
    _description = 'Fee Slip Generation Wizard'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    amount_to_pay = fields.Float(string="Amount to Pay", digits='Product Price')
    installment = fields.Integer(string="Installment")
    payment_term = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annualy', 'Annually'),
        ('custom', 'Custom')
        ], string='Payment Term', required=True)
    enrollment_id = fields.Many2one('student.enrollment', 'Enrollment')
    student_id = fields.Many2one(related='enrollment_id.student_id')

    @staticmethod
    def get_total_periods(payment_term, installment=None, start_date=None, end_date=None):
        if not start_date or not end_date:
            return 1
        if payment_term == 'monthly':
            months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
            if end_date.day > start_date.day:
                months += 1
            return max(1, months)
        elif payment_term == 'quarterly':
            total_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
            if end_date.day > start_date.day:
                total_months += 1
            quarters = math.ceil(total_months / 3)
            return max(1, quarters)
        elif payment_term == 'custom':
            return installment or 1
        else:
            return 1
        
    def prepare_fee_slip(self, is_first_slip, current_period=1, one_time_fees=None, recurring_fees=None):
        """Prepare values for a fee slip based on payment term, period, and fee summary."""
        self.ensure_one()
        date_from = date_to = False

        if self.payment_term == 'monthly':
            date_from = self.start_date + relativedelta(months=current_period - 1)
            date_to = date_from + relativedelta(months=1, days=-1)
            if date_from > self.end_date:
                return None
            if date_to > self.end_date:
                date_to = self.end_date

        elif self.payment_term == 'quarterly':
            date_from = self.start_date + relativedelta(months=(current_period - 1) * 3)
            date_to = date_from + relativedelta(months=3, days=-1)
            if date_from > self.end_date:
                return None
            if date_to > self.end_date:
                date_to = self.end_date

        elif self.payment_term == 'annualy':
            date_from = self.start_date
            date_to = self.end_date
        elif self.payment_term == 'custom' and self.installment:
            total_days = (self.end_date - self.start_date).days + 1
            days_per_installment = total_days // self.installment
            date_from = self.start_date + relativedelta(days=(current_period - 1) * days_per_installment)
            date_to = self.end_date if current_period == self.installment else date_from + relativedelta(days=days_per_installment - 1)

        slip_vals = {
            'enrollment_id': self.enrollment_id.id,
            'fee_slip_line_ids': [],
            'date_from': date_from,
            'date_to': date_to,
        }

        if one_time_fees:
            for summary in one_time_fees:
                slip_vals['fee_slip_line_ids'].append((0, 0, {
                    'product_id': summary.product_id.id,
                    'fee': math.ceil(summary.fee)
                }))

        if recurring_fees:
            installment_count = self.get_total_periods(
                self.payment_term, self.installment, self.start_date, self.end_date)
            for summary in recurring_fees:
                total = summary.fee
                raw = total / installment_count
                ceil_fees = [math.ceil(raw)] * (installment_count - 1)
                last_fee = total - sum(ceil_fees)
                all_installments = ceil_fees + [last_fee]
                current_fee = all_installments[current_period - 1]
                slip_vals['fee_slip_line_ids'].append((0, 0, {
                    'product_id': summary.product_id.id,
                    'fee': current_fee
                }))        
        return slip_vals

    def generate_now(self):
        if self.enrollment_id.generated_amount == self.enrollment_id.total_amount:
            return

        total_periods = self.get_total_periods(
            self.payment_term, self.installment, self.start_date, self.end_date)
        paid_slips = self.enrollment_id.fee_slip_ids.filtered(lambda s: s.state == 'paid')
        unpaid_slips = self.enrollment_id.fee_slip_ids.filtered(lambda s: s.state != 'paid')
        paid_one_time_product_ids = set(paid_slips.mapped('fee_slip_line_ids.product_id.id'))

        one_time_fees = self.enrollment_id.fee_summary_ids.filtered(lambda s: s.frequency == 'one')
        new_one_time_fees = one_time_fees.filtered(lambda s: s.product_id.id not in paid_one_time_product_ids)

        unpaid_slips.unlink()
        paid_count = len(paid_slips)
        slips_to_generate = total_periods - paid_count
        recurring_fees = self.enrollment_id.fee_summary_ids.filtered(lambda s: s.frequency == 'multi')

        if slips_to_generate > 0:
            for period in range(paid_count + 1, total_periods + 1):
                is_first_new = (period == paid_count + 1)
                slip_vals = self.prepare_fee_slip(
                    is_first_slip=is_first_new,
                    current_period=period,
                    one_time_fees=new_one_time_fees if is_first_new else None,
                    recurring_fees=recurring_fees
                )
                if not slip_vals:
                    continue
                if slip_vals['fee_slip_line_ids']:
                    self.env['wk.fee.slip'].create(slip_vals)

        elif not unpaid_slips and new_one_time_fees:
            slip_vals = self.prepare_fee_slip(
                is_first_slip=False,
                current_period=paid_count + 1,
                one_time_fees=new_one_time_fees,
                recurring_fees=None
            )
            if slip_vals['fee_slip_line_ids']:
                self.env['wk.fee.slip'].create(slip_vals)

        self.enrollment_id.generated_amount = sum(self.enrollment_id.fee_slip_ids.mapped('total_amount'))
        self.enrollment_id.payment_term = self.payment_term
        self.enrollment_id.installment = self.installment
    
