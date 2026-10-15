# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import ValidationError
from odoo.addons.utilities_collection.time import days360
from dateutil.relativedelta import relativedelta
import calendar


class HrConcept(models.Model):
    _inherit = 'hr.concept'

    def _VAC_LIQ(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        settlement_date = data_payslip['contract'].settlement_date
        if not settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        logs = self._initialize_logs(data_payslip)
        if not data_payslip['politics']['hr_payroll_co.total_avg_holidays']:
            if 'last_year' not in data_payslip:
                self.get_last_year(data_payslip, settlement_date, True, logs)
            average = data_payslip['last_year']['average']
        else:
            self.get_last_year_holidays(
                data_payslip, settlement_date, True, logs)
            average = data_payslip['last_year_vac']['average']
        if 'holiday_book' not in data_payslip:
            self.get_holiday_book(data_payslip, settlement_date)
        days_left = data_payslip['holiday_book']['days_left']

        # Discount current no pay days
        no_pay_days = len(self.env['hr.leave.line'].search([
            ('period_id', '=', data_payslip['period'].id),
            ('contract_id', '=', data_payslip['contract'].id),
            ('state', '=', 'validated'),
            ('leave_id.category_type', '=', 'NO_PAY')
        ]))
        current_days_left = -no_pay_days * 15 / \
            data_payslip['contract'].get_benefits_days_base()
        days_left += current_days_left

        logs['holidays_days_left'] = days_left
        logs['total'] = average * days_left
        data_payslip['VAC_LIQ'] = average * days_left

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': average,
            'qty': days_left,
            'rate': 100,
            'total': average * days_left,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PRIMA_LIQ(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        logs = self._initialize_logs(data_payslip)
        date_to = data_payslip['contract'].settlement_date
        from_month = 1 if data_payslip['period'].start.month <= 6 else 7
        date_from = data_payslip['period'].start.replace(
            month=from_month, day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
            date_from = data_payslip['contract'].apprentice_to_worker_date

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)

        total_previous = {}
        to_month = 6 if data_payslip['period'].start.month <= 6 else 12
        to_day = 30 if data_payslip['period'].start.month <= 6 else 31
        date_to_previous = data_payslip['period'].start.replace(
            month=to_month, day=to_day)
        concepts_previuos = ('PRIMA', 'PRIMA_LIQ')
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': date_to_previous}, data_payslip['contract'].id, concepts_previuos)
        total -= sum(total_previous.values())
        logs['total'] = total
        data_payslip['PRIMA_LIQ'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PRIMA(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        logs = self._initialize_logs(data_payslip)
        from_month = 1 if data_payslip['period'].start.month <= 6 else 7
        to_month = 6 if data_payslip['period'].start.month <= 6 else 12
        to_day = 30 if data_payslip['period'].start.month <= 6 else 31
        date_from = data_payslip['period'].start.replace(
            month=from_month, day=1)
        date_to = data_payslip['period'].start.replace(
            month=to_month, day=to_day)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
            date_from = data_payslip['contract'].apprentice_to_worker_date
        if data_payslip['cutoff_date']:
            date_to = data_payslip['cutoff_date']
        if data_payslip['contract'].settlement_date and data_payslip['contract'].settlement_date < date_to:
            date_to = data_payslip['contract'].settlement_date
        
        if date_from > date_to:
            return

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)
        total_previous = {}
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRIMA',))
        total -= total_previous.get('PRIMA', 0)
        logs['total'] = total
        data_payslip['PRIMA'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PRIMA_CONV(self, data_payslip):
        apply_prim_conv = data_payslip['politics']['hr_payroll_co.apply_prim_conv']
        if not apply_prim_conv:
            return

        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        if data_payslip['period'].start.month not in (5, 6, 11, 12):
            return

        if not data_payslip['contract'].is_conventional:
            return

        logs = self._initialize_logs(data_payslip)
        days_ref = data_payslip['politics']['hr_payroll_co.days_in_prim_conv']
        from_month = 1 if data_payslip['period'].start.month <= 6 else 7
        to_month = 6 if data_payslip['period'].start.month <= 6 else 12
        to_day = 30 if data_payslip['period'].start.month <= 6 else 31
        date_from = data_payslip['period'].start.replace(
            month=from_month, day=1)
        date_to = data_payslip['period'].start.replace(
            month=to_month, day=to_day)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        ignore_rest_days = data_payslip['politics']['hr_payroll_co.discount_all_leave_in_social_benefits']
        days = days360(date_from, date_to)
        days_not_worked = self.env['hr.leave.line'].get_days_not_worked(
            data_payslip['contract'], date_from, date_to, ignore_rest_days, data_payslip, False)
        days -= days_not_worked
        base = data_payslip['contract'].wage
        if base <= smmlv * 2:
            subsidy = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['current_year_month']]
            base += subsidy
        qty = (days * days_ref) / 180
        total = qty * (base / 30)

        total_previous = {}
        is_second_period = data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'SECOND'
        date_from_previous = data_payslip['period'].start.replace(
            day=1) if is_second_period else data_payslip['period'].start
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRIMA_CONV',))
        total -= total_previous.get('PRIMA_CONV', 0)
        if round(total) == 0 and data_payslip['period'].start.month in (6, 12):
            return
        logs['total'] = total
        data_payslip['PRIMA_CONV'] = total
        logs['date_from'] = date_from
        logs['date_to'] = date_to
        logs['total_base'] = base
        logs['worked_days'] = days
        logs['no_pay_leave_days'] = days_not_worked

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PRIMA_VAC_CONV(self, data_payslip):
        apply_prim_conv = data_payslip['politics']['hr_payroll_co.apply_prim_conv']
        if not apply_prim_conv:
            return

        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if not data_payslip['contract'].is_conventional:
            return

        days_ref = data_payslip['politics']['hr_payroll_co.days_in_prim_vac_conv']
        logs = self._initialize_logs(data_payslip)
        date_from = data_payslip['contract'].date_start
        date_to = data_payslip['period'].end

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        ignore_rest_days = data_payslip['politics']['hr_payroll_co.discount_all_leave_in_social_benefits']
        days = days360(date_from, date_to)
        base = data_payslip['contract'].wage
        if base <= smmlv * 2:
            subsidy = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['current_year_month']]
            base += subsidy
        qty = (days * days_ref) / 360
        total = qty * (base / 30)

        total_previous = {}
        is_second_period = data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'SECOND'
        date_from_previous = data_payslip['period'].start.replace(
            day=1) if is_second_period else data_payslip['period'].start
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRIMA_VAC_CONV',))
        total -= total_previous.get('PRIMA_VAC_CONV', 0)
        logs['total'] = total
        data_payslip['PRIMA_VAC_CONV'] = round(total)
        logs['date_from'] = date_from
        logs['date_to'] = date_to
        logs['total_base'] = base
        logs['worked_days'] = days

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PRIMA_VAC_LIQ_CONV(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if not data_payslip['contract'].is_conventional:
            return

        logs = self._initialize_logs(data_payslip)
        date_from = data_payslip['contract'].date_start
        date_to = data_payslip['contract'].settlement_date

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        ignore_rest_days = data_payslip['politics']['hr_payroll_co.discount_all_leave_in_social_benefits']
        days = days360(date_from, date_to)
        base = data_payslip['contract'].wage
        if base <= smmlv * 2:
            subsidy = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['current_year_month']]
            base += subsidy
        qty = (days * 30) / 360
        total = qty * (base / 30)

        total_previous = {}
        is_second_period = data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'SECOND'
        date_from_previous = data_payslip['period'].start.replace(
            day=1) if is_second_period else data_payslip['period'].start
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': date_to}, data_payslip['contract'].id, ('PRIMA_VAC_CONV', 'PRIMA_VAC_LIQ_CONV'))
        total -= total_previous.get('PRIMA_VAC_CONV', 0)
        logs['total'] = total
        data_payslip['PRIMA_VAC_CONV'] = round(total)
        logs['date_from'] = date_from
        logs['date_to'] = date_to
        logs['total_base'] = base
        logs['worked_days'] = days

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PRIMA_LIQ_CONV(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        if not data_payslip['contract'].is_conventional:
            return

        logs = self._initialize_logs(data_payslip)
        from_month = 1 if data_payslip['period'].start.month <= 5 else 7
        date_from = data_payslip['period'].start.replace(
            month=from_month, day=1)
        date_to = data_payslip['contract'].settlement_date
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        ignore_rest_days = data_payslip['politics']['hr_payroll_co.discount_all_leave_in_social_benefits']
        days = days360(date_from, date_to)
        days_not_worked = self.env['hr.leave.line'].get_days_not_worked(
            data_payslip['contract'], date_from, date_to, ignore_rest_days, data_payslip, False)
        days -= days_not_worked
        base = data_payslip['contract'].wage
        if base <= smmlv * 2:
            subsidy = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['current_year_month']]
            base += subsidy
        qty = (days * 24) / 180
        total = qty * (base / 30)

        total_previous = {}
        is_second_period = data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'SECOND'
        date_from_previous = data_payslip['period'].start.replace(
            day=1) if is_second_period else data_payslip['period'].start
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRIMA_CONV', 'PRIMA_LIQ_CONV'))
        total -= total_previous.get('PRIMA_CONV', 0)
        total -= total_previous.get('PRIMA_LIQ_CONV', 0)
        logs['total'] = total
        data_payslip['PRIMA_LIQ_CONV'] = round(total)
        logs['date_from'] = date_from
        logs['date_to'] = date_to
        logs['total_base'] = base
        logs['worked_days'] = days
        logs['no_pay_leave_days'] = days_not_worked

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PROV_PRIMA_VAC_CONV(self, data_payslip):
        apply_prim_conv = data_payslip['politics']['hr_payroll_co.apply_prim_conv']
        if not apply_prim_conv:
            return

        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if not data_payslip['contract'].is_conventional:
            return

        percentage_conv = data_payslip['politics']['hr_payroll_co.percentage_prv_prim_conv']

        logs = self._initialize_logs(data_payslip)
        date_to = data_payslip['period'].end
        if data_payslip['contract'].settlement_date and data_payslip['contract'].settlement_date < date_to:
            date_to = data_payslip['contract'].settlement_date
        date_from = data_payslip['period'].start
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        ignore_rest_days = data_payslip['politics']['hr_payroll_co.discount_all_leave_in_social_benefits']
        days = days360(date_from, date_to)
        days_not_worked = self.env['hr.leave.line'].get_days_not_worked(
            data_payslip['contract'], date_from, date_to, ignore_rest_days, data_payslip, False)
        days -= days_not_worked
        base = data_payslip['contract'].wage
        if base <= smmlv * 2:
            subsidy = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['current_year_month']]
            base += subsidy
        total = base * (percentage_conv / 100)

        total_previous = {}
        is_second_period = data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'SECOND'
        date_from_previous = data_payslip['period'].start.replace(
            day=1) if is_second_period else data_payslip['period'].start
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': date_to}, data_payslip['contract'].id, ('PROV_PRIMA_VAC_CONV',))
        total -= total_previous.get('PROV_PRIMA_VAC_CONV', 0)
        logs['total'] = total
        data_payslip['PROV_PRIMA_VAC_CONV'] = total
        logs['date_from'] = date_from
        logs['date_to'] = date_to
        logs['total_base'] = base
        logs['worked_days'] = days
        logs['no_pay_leave_days'] = days_not_worked

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': 100,
            'rate': percentage_conv,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PROV_PRIMA_VAC_LIQ_CONV(self, data_payslip):
        apply_prim_conv = data_payslip['politics']['hr_payroll_co.apply_prim_conv']
        if not apply_prim_conv:
            return

        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if not data_payslip['contract'].is_conventional:
            return

        percentage_conv = data_payslip['politics']['hr_payroll_co.percentage_prv_prim_liq_conv']

        logs = self._initialize_logs(data_payslip)
        date_to = data_payslip['period'].end
        if data_payslip['contract'].settlement_date and data_payslip['contract'].settlement_date < date_to:
            date_to = data_payslip['contract'].settlement_date
        date_from = data_payslip['period'].start
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        ignore_rest_days = data_payslip['politics']['hr_payroll_co.discount_all_leave_in_social_benefits']
        days = days360(date_from, date_to)
        days_not_worked = self.env['hr.leave.line'].get_days_not_worked(
            data_payslip['contract'], date_from, date_to, ignore_rest_days, data_payslip, False)
        days -= days_not_worked
        base = data_payslip['contract'].wage
        if base <= smmlv * 2:
            subsidy = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['current_year_month']]
            base += subsidy
        total = base * (percentage_conv / 100)

        total_previous = {}
        is_second_period = data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'SECOND'
        date_from_previous = data_payslip['period'].start.replace(
            day=1) if is_second_period else data_payslip['period'].start
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': date_to}, data_payslip['contract'].id, ('PROV_PRIMA_VAC_LIQ_CONV',))
        total -= total_previous.get('PROV_PRIMA_VAC_LIQ_CONV', 0)
        logs['total'] = total
        data_payslip['PROV_PRIMA_VAC_LIQ_CONV'] = total
        logs['date_from'] = date_from
        logs['date_to'] = date_to
        logs['total_base'] = base
        logs['worked_days'] = days
        logs['no_pay_leave_days'] = days_not_worked

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': 100,
            'rate': percentage_conv,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _CES(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        if data_payslip['period'].end.month not in (1, 2, 12):
            raise ValidationError(
                'Las cesantias solo se pueden calcular en nominas de Diciembre, Enero o Febrero.')

        if data_payslip['period'].end.month != 12:
            date_ref = data_payslip['period'].end - relativedelta(years=1)
        else:
            date_ref = data_payslip['period'].end
        date_from = date_ref.replace(month=1, day=1)
        date_to = date_ref.replace(month=12, day=31)

        if date_to < data_payslip['contract'].date_start:
            return

        logs = self._initialize_logs(data_payslip)

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        
        if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
            date_from = data_payslip['contract'].apprentice_to_worker_date

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        base, qty, accrued_ces = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)

        payment_period = {'start': data_payslip['period'].end.replace(
            month=1, day=1), 'end': data_payslip['period'].end}
        total_previous = {}
        concepts = ('CES',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
        ces_paid = total_previous.get('CES', 0)

        last_year_period = {'start': date_from, 'end': date_to}
        total_previous = {}
        concepts = ('CES_PART',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, last_year_period, data_payslip['contract'].id, concepts)
        ces_part_paid = total_previous.get('CES_PART', 0)

        data_payslip['accrued_ces'] = (
            accrued_ces, qty, last_year_period, payment_period)
        data_payslip['accrued_ces_amount'] = accrued_ces
        total = accrued_ces - ces_paid - ces_part_paid
        data_payslip['CES'] = total
        logs['total'] = total
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _ICES(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        if data_payslip['period'].end.month not in (1, 2, 12):
            raise ValidationError(
                'Los intereses de cesantias solo se pueden calcular en nominas de Diciembre, Enero o Febrero.')

        logs = self._initialize_logs(data_payslip)

        if data_payslip['period'].end.month != 12:
            date_ref = data_payslip['period'].end - relativedelta(years=1)
        else:
            date_ref = data_payslip['period'].end
        date_from = date_ref.replace(month=1, day=1)
        date_to = date_ref.replace(month=12, day=31)

        if date_to < data_payslip['contract'].date_start:
            return

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
            date_from = data_payslip['contract'].apprentice_to_worker_date

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)

        last_year_period = {'start': date_from, 'end': date_to}
        payment_period = {'start': data_payslip['period'].end.replace(
            month=1, day=1), 'end': data_payslip['period'].end}

        accrued_ces, qty, last_year_period, payment_period = total, qty, last_year_period, payment_period
        accrued_ces_amount = data_payslip.get('accrued_ces_amount', 0.0)
        if not accrued_ces_amount:
            accrued_ces_amount = accrued_ces
        rate = 0.12 * qty / data_payslip['contract'].get_benefits_days_base()
        accrued_ices = accrued_ces_amount * rate

        total = accrued_ices

        if data_payslip['period'].end.month != 12:
            total_previous = {}
            concepts = ('ICES',)
            self._get_total_concepts(
                data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
            ices_paid = total_previous.get('ICES', 0)

            total_previous = {}
            concepts = ('ICES_PART',)
            self._get_total_concepts(
                data_payslip['cr'], total_previous, last_year_period, data_payslip['contract'].id, concepts)
            ices_part_paid = total_previous.get('ICES_PART', 0)

            total -= ices_paid - ices_part_paid
        elif data_payslip['period'].end.month == 12:
            total_previous = {}
            concepts = ('ICES_PART',)
            self._get_total_concepts(
                data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
            ices_part_paid = total_previous.get('ICES_PART', 0)

            total -= ices_part_paid

        logs['rate'] = rate * 100
        logs['total'] = total if total > 0 else 0

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': accrued_ces,
            'qty': 1,
            'rate': rate * 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _CESLY(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        date_ref = data_payslip['period'].end - relativedelta(years=1)
        date_from = date_ref.replace(month=1, day=1)
        date_to = date_ref.replace(month=12, day=31)

        if date_to < data_payslip['contract'].date_start:
            return

        logs = self._initialize_logs(data_payslip)

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date and data_payslip['contract'].settlement_date.month == date_to.month and data_payslip['contract'].settlement_date.year == date_to.year:
            date_to = data_payslip['contract'].settlement_date

        if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
            date_from = data_payslip['contract'].apprentice_to_worker_date

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        base, qty, accrued_cesly = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)

        payment_period = {'start': data_payslip['period'].end.replace(
            month=1, day=1), 'end': data_payslip['period'].end}
        total_previous = {}
        concepts = ('CESLY',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
        cesly_paid = sum(total_previous.values())

        last_year_period = {'start': date_from, 'end': date_to}
        total_previous = {}
        concepts = ('CES_PART',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, last_year_period, data_payslip['contract'].id, concepts)
        ces_part_paid = total_previous.get('CES_PART', 0)

        data_payslip['accrued_cesly'] = (
            accrued_cesly, qty, last_year_period, payment_period)

        total = accrued_cesly - cesly_paid - ces_part_paid
        logs['total'] = total
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _ICESLY(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        if 'accrued_cesly' not in data_payslip:
            date_ref = data_payslip['period'].end - relativedelta(years=1)
            date_from = date_ref.replace(month=1, day=1)
            date_to = date_ref.replace(month=12, day=31)

            if date_to < data_payslip['contract'].date_start:
                return

            if date_from < data_payslip['contract'].date_start:
                date_from = data_payslip['contract'].date_start
            if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date:
                date_to = data_payslip['contract'].settlement_date

            if fiscal_code == '19':
                labor_reform_start_date = self.get_labor_reform_start_date()
                if date_from < labor_reform_start_date:
                    date_from = labor_reform_start_date

            base, qty, accrued_cesly = self._compute_social_benefits(
                data_payslip, date_from, date_to)

            last_year_period = {'start': date_from, 'end': date_to}
            payment_period = {'start': data_payslip['period'].end.replace(
                month=1, day=1), 'end': data_payslip['period'].end}
            data_payslip['accrued_cesly'] = (
                accrued_cesly, qty, last_year_period, payment_period)

        accrued_cesly, qty, last_year_period, payment_period = data_payslip['accrued_cesly']
        rate = 0.12 * qty / data_payslip['contract'].get_benefits_days_base()
        accrued_icesly = accrued_cesly * rate

        total_previous = {}
        concepts = ('ICESLY',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
        icesly_paid = total_previous.get('ICESLY', 0)

        total_previous = {}
        concepts = ('ICES_PART',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, last_year_period, data_payslip['contract'].id, concepts)
        ices_part_paid = total_previous.get('ICES_PART', 0)

        total = accrued_icesly - icesly_paid - ices_part_paid

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': accrued_cesly,
            'qty': 1,
            'rate': rate * 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _CES_LIQ(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        logs = self._initialize_logs(data_payslip)
        date_to = data_payslip['contract'].settlement_date
        date_from = data_payslip['period'].start.replace(month=1, day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

            # La etapa lectiva no causa cesantias
            if (data_payslip['contract'].apprentice_to_worker_date
                    and data_payslip['contract'].apprentice_to_worker_date > date_from):
                date_from = data_payslip['contract'].apprentice_to_worker_date

        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)

        current_period = {'start': date_from, 'end': date_to}

        total_previous = {}
        previous_concepts = ('CES_LIQ', 'CES_PART')
        partial_period = dict(current_period)
        consignment_cutoff = self._get_ces_consignment_cutoff(
            data_payslip['cr'], data_payslip['contract'].id, current_period)
        if consignment_cutoff:
            partial_period['start'] = consignment_cutoff
        self._get_total_concepts(
            data_payslip['cr'], total_previous, partial_period, data_payslip['contract'].id, previous_concepts)
        total -= sum(total_previous.values())
        data_payslip['accrued_ces_liq'] = (total, qty, current_period)
        data_payslip['accrued_ces_liq_total'] = total
        logs['total'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _ICES_LIQ(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        logs = self._initialize_logs(data_payslip)
        date_to = data_payslip['contract'].settlement_date
        date_from = data_payslip['period'].start.replace(month=1, day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

            # La etapa lectiva no causa cesantias
            if (data_payslip['contract'].apprentice_to_worker_date
                    and data_payslip['contract'].apprentice_to_worker_date > date_from):
                date_from = data_payslip['contract'].apprentice_to_worker_date

        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)

        accrued_ces_liq_total = data_payslip.get('accrued_ces_liq_total', 0.0)

        if data_payslip['politics']['hr_payroll_co.intces_days_with_last_page']:
            last_partial_date = self._get_last_paid_concept(
                data_payslip['cr'], data_payslip['contract'].id, 'CES_PART', date_from, date_to)
            if last_partial_date:
                qty = days360(last_partial_date + relativedelta(days=1), date_to)

        rate = 0.12 * qty / data_payslip['contract'].get_benefits_days_base()
        total = accrued_ces_liq_total * rate

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': accrued_ces_liq_total,
            'qty': qty,
            'rate': rate * 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _CES_PART(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        date_to = data_payslip['period'].end
        date_from = data_payslip['period'].start.replace(month=1, day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to)

        current_period = {'start': date_from, 'end': date_to}
        data_payslip['accrued_ces_part'] = (total, qty, current_period)

        total_previous = {}
        concepts = ('CES_PART',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, current_period, data_payslip['contract'].id, concepts)
        total -= total_previous.get('CES_PART', 0)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _ICES_PART(self, data_payslip):
        if 'accrued_ces_part' not in data_payslip:
            raise ValidationError(
                'No se ha calculado cesantías parciales')

        accrued_ces_part, qty, current_period = data_payslip['accrued_ces_part']
        rate = 0.12 * qty / data_payslip['contract'].get_benefits_days_base()
        total = accrued_ces_part * rate

        total_previous = {}
        concepts = ('ICES_PART',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, current_period, data_payslip['contract'].id, concepts)
        total -= total_previous.get('CES_PART', 0)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': accrued_ces_part,
            'qty': 1,
            'rate': rate * 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _PRV_CES(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        logs = self._initialize_logs(data_payslip)
        date_to = data_payslip['period'].end
        if data_payslip['contract'].settlement_date and data_payslip['contract'].settlement_date < date_to:
            date_to = data_payslip['contract'].settlement_date
        date_from = data_payslip['period'].start.replace(month=1, day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if data_payslip['contract'].fiscal_type_id.code == '19' and data_payslip['contract'].apprentice_to_worker_date:
            if data_payslip['contract'].apprentice_to_worker_date > date_from:
                date_from = data_payslip['contract'].apprentice_to_worker_date

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        logs['date_from'] = str(date_from)
        logs['date_to'] = str(date_to)

        if data_payslip.get('politics', {}).get('hr_payroll_co.compute_simple_provisions', False):
            rate = data_payslip['politics']['hr_payroll_co.severance_percentage']/100
            interest_rate = data_payslip['politics']['hr_payroll_co.interest_severance_percentage']/100

            if 'GENERAL_IBC' not in data_payslip:
                data_payslip['GENERAL_IBC'], data_payslip['GENERAL_IBC_VAC'] = self.get_general_ibc(
                    data_payslip, apply_25_smmlv_cap=False)

            ibd = data_payslip['GENERAL_IBC']

            wage_teaching = self._get_wage_in_teaching_phase(data_payslip)
            ibd -= wage_teaching

            smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
            if data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'FIRST':
                smmlv = (smmlv / 30) * 15
            if ibd <= 2 * smmlv:
                date_start = data_payslip['period'].start.replace(day=1)
                if data_payslip['contract'].fiscal_type_id.code == '19' and data_payslip['contract'].apprentice_to_worker_date:
                    if data_payslip['contract'].apprentice_to_worker_date > date_start:
                        date_start = data_payslip['contract'].apprentice_to_worker_date
                _, last_day = calendar.monthrange(
                    data_payslip['period'].end.year, data_payslip['period'].end.month)
                date_end = data_payslip['period'].end.replace(day=last_day)

                hr_payslip = self.env['hr.payslip'].search([
                    ('contract_id', '=', data_payslip['contract'].id),
                    ('liquidation_date', '>=', date_start),
                    ('liquidation_date', '<=', date_end),
                    ('id', '!=', data_payslip['payslip_id'])
                ])
                for payslip in hr_payslip.filtered(lambda x: x.period_id.start < data_payslip['period'].end):
                    ibd += sum([sub.total for sub in payslip.payslip_line_ids if sub.name == 'SUBSIDIO DE TRANSPORTE'])
                ibd += data_payslip.get('SUB_TRANS', 0)

            payment_period = {
                'start': data_payslip['period'].end.replace(day=1),
                'end': data_payslip['period'].end
            }
            total_previous = {}
            concepts = ('PRV_CES',)
            self._get_total_concepts(
                data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
            prv_ces_paid = total_previous.get('PRV_CES', 0)

            prov_ces_total = (ibd * rate) - prv_ces_paid
            interest = prov_ces_total * interest_rate
            data_payslip['PRV_ICES'] = (
                interest, date_from, date_to, interest_rate)

            logs['total_earnings'] = data_payslip.get("earnings", 0)
            logs['total_comp_earnings'] = data_payslip.get("comp_earnings", 0)
            logs['total_o_salarial_earnings'] = data_payslip.get(
                "o_salarial_earnings", 0)
            logs['total_o_rights'] = data_payslip.get("o_rights", 0)
            logs['total_o_earnings'] = data_payslip.get("o_earnings", 0)
            logs['ibd'] = ibd
            logs['rate'] = rate * 100
            logs['total_base'] = ibd
            logs['total'] = prov_ces_total

            return {
                'name': self.name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': ibd,
                'qty': 1,
                'rate': rate * 100,
                'total': prov_ces_total,
                'origin': 'local',
                'concept_id': self.id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
                'log_ids': logs,
            }

        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)

        if data_payslip['contract'].fiscal_type_id.code == '19' and data_payslip['contract'].apprentice_to_worker_date:
            if data_payslip['contract'].apprentice_to_worker_date > date_from:
                date_from = data_payslip['contract'].apprentice_to_worker_date

        current_period = {'start': date_from, 'end': date_to}
        data_payslip['accrued_prv_ces_liq'] = (total, qty, current_period)

        total_previous = {}
        previous_concepts = ('PRV_CES',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, current_period, data_payslip['contract'].id, previous_concepts)
        total -= sum(total_previous.values())
        logs['total'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PRV_ICES(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        logs = self._initialize_logs(data_payslip)

        if data_payslip.get('politics', {}).get('hr_payroll_co.compute_simple_provisions', False):
            if 'PRV_ICES' not in data_payslip:
                raise ValidationError(
                    'No se ha calculado la provisión de cesantías')

            interest, date_from, date_to, rate_worked_days = data_payslip['PRV_ICES']

            if not data_payslip.get('politics', {}).get('hr_payroll_co.compute_simple_provisions', False):
                provision_interest = self._get_total_previous(
                    data_payslip, date_from, date_to)
            else:
                provision_interest = 0

            total = interest - provision_interest

            logs['date_from'] = str(date_from)
            logs['date_to'] = str(date_to)
            logs['total_base'] = interest
            logs['rate'] = rate_worked_days * 100
            logs['total'] = total

            return {
                'name': self.name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': interest,
                'qty': 1,
                'rate': rate_worked_days * 100,
                'total': total,
                'origin': 'local',
                'concept_id': self.id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
                'log_ids': logs,
            }

        if 'accrued_prv_ces_liq' not in data_payslip:
            raise ValidationError(
                'No se ha calculado cesantías de liquidación')
        accrued_ces_liq, qty, current_period = data_payslip['accrued_prv_ces_liq']
        rate = 0.12 * qty / data_payslip['contract'].get_benefits_days_base()
        total = accrued_ces_liq * rate

        total_previous = {}
        previous_concepts = ('PRV_ICES',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, current_period, data_payslip['contract'].id, previous_concepts)
        total -= sum(total_previous.values())

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': accrued_ces_liq,
            'qty': qty,
            'rate': rate * 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _PRV_PRIMA(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            return

        logs = self._initialize_logs(data_payslip)

        if data_payslip.get('politics', {}).get('hr_payroll_co.compute_simple_provisions', False):
            rate = data_payslip['politics']['hr_payroll_co.prima_percentage'] / 100

            if 'GENERAL_IBC' not in data_payslip:
                data_payslip['GENERAL_IBC'], data_payslip['GENERAL_IBC_VAC'] = self.get_general_ibc(
                    data_payslip, apply_25_smmlv_cap=False)

            ibd = data_payslip['GENERAL_IBC']

            wage_teaching = self._get_wage_in_teaching_phase(data_payslip)
            ibd -= wage_teaching

            smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
            if data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'FIRST':
                smmlv = (smmlv / 30) * 15
            if ibd <= 2 * smmlv:
                date_start = data_payslip['period'].start.replace(day=1)
                _, last_day = calendar.monthrange(
                    data_payslip['period'].end.year, data_payslip['period'].end.month)
                date_end = data_payslip['period'].end.replace(day=last_day)

                hr_payslip = self.env['hr.payslip'].search([
                    ('contract_id', '=', data_payslip['contract'].id),
                    ('liquidation_date', '>=', date_start),
                    ('liquidation_date', '<=', date_end),
                    ('id', '!=', data_payslip['payslip_id'])
                ])
                for payslip in hr_payslip.filtered(lambda x: x.period_id.start < data_payslip['period'].end):
                    ibd += sum([sub.total for sub in payslip.payslip_line_ids if sub.name == 'SUBSIDIO DE TRANSPORTE'])
                ibd += data_payslip.get('SUB_TRANS', 0)

            payment_period = {
                'start': data_payslip['period'].end.replace(day=1),
                'end': data_payslip['period'].end
            }
            total_previous = {}
            concepts = ('PRV_PRIMA',)
            self._get_total_concepts(
                data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
            prv_prima_paid = total_previous.get('PRV_PRIMA', 0)

            prov_prima_total = (ibd * rate) - prv_prima_paid

            date_to = data_payslip['period'].end
            if data_payslip['contract'].settlement_date and data_payslip['contract'].settlement_date < date_to:
                date_to = data_payslip['contract'].settlement_date
            date_from = data_payslip['period'].start.replace(month=1, day=1)
            if date_from < data_payslip['contract'].date_start:
                date_from = data_payslip['contract'].date_start

            if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
                date_from = data_payslip['contract'].apprentice_to_worker_date

            if fiscal_code == '19':
                labor_reform_start_date = self.get_labor_reform_start_date()
                if date_from < labor_reform_start_date:
                    date_from = labor_reform_start_date

            logs['date_from'] = str(date_from)
            logs['date_to'] = str(date_to)
            logs['total_earnings'] = data_payslip.get("earnings", 0)
            logs['total_comp_earnings'] = data_payslip.get("comp_earnings", 0)
            logs['total_o_salarial_earnings'] = data_payslip.get(
                "o_salarial_earnings", 0)
            logs['total_o_rights'] = data_payslip.get("o_rights", 0)
            logs['total_o_earnings'] = data_payslip.get("o_earnings", 0)
            logs['ibd'] = ibd
            logs['rate'] = rate * 100
            logs['total_base'] = ibd
            logs['total'] = prov_prima_total

            return {
                'name': self.name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': ibd,
                'qty': 1,
                'rate': rate * 100,
                'total': prov_prima_total,
                'origin': 'local',
                'concept_id': self.id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
                'log_ids': logs,
            }

        date_to = data_payslip['period'].end
        if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date:
            date_to = data_payslip['contract'].settlement_date
        from_month = 1 if data_payslip['period'].start.month <= 6 else 7
        date_from = data_payslip['period'].start.replace(
            month=from_month, day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        
        if data_payslip['contract'].fiscal_type_id.code == '19' and data_payslip['contract'].apprentice_to_worker_date:
            if data_payslip['contract'].apprentice_to_worker_date > date_from:
                date_from = data_payslip['contract'].apprentice_to_worker_date

        if fiscal_code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to, True, logs)

        total_previous = {}
        concepts_previuos = ('PRV_PRIMA',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts_previuos)
        total -= sum(total_previous.values())
        logs['total'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PRV_VAC(self, data_payslip):
        fiscal_code = data_payslip['contract'].fiscal_type_id.code
        if fiscal_code in ('12', '23'):
            return

        if not self._apply_labor_reform(data_payslip) and fiscal_code == '19':
            return

        logs = self._initialize_logs(data_payslip)

        if data_payslip.get('politics', {}).get('hr_payroll_co.compute_simple_provisions', False):
            rate = data_payslip['politics']['hr_payroll_co.holidays_percentage'] / 100

            general_ibc, general_ibc_vac = self.get_general_ibc(
                data_payslip, apply_25_smmlv_cap=False)

            if data_payslip['contract'].contract_type_id.type_class == 'int':
                ibd = general_ibc_vac
            else:
                ibd = general_ibc

            wage_teaching = self._get_wage_in_teaching_phase(data_payslip)
            ibd -= wage_teaching

            payment_period = {
                'start': data_payslip['period'].end.replace(day=1),
                'end': data_payslip['period'].end
            }
            total_previous = {}
            concepts = ('PRV_VAC',)
            self._get_total_concepts(
                data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
            prv_vac_paid = total_previous.get('PRV_VAC', 0)

            prov_vac_total = (ibd * rate) - prv_vac_paid

            date_to = data_payslip['contract'].settlement_date
            date_from = data_payslip['contract'].date_start
            if not date_to or date_to > data_payslip['period'].end:
                date_to = data_payslip['period'].end - relativedelta(months=1)

            if fiscal_code == '19':
                labor_reform_start_date = self.get_labor_reform_start_date()
                if date_from < labor_reform_start_date:
                    date_from = labor_reform_start_date

            logs['date_from'] = str(date_from)
            logs['date_to'] = str(date_to)
            logs['total_earnings'] = data_payslip.get("earnings", 0)
            logs['total_comp_earnings'] = data_payslip.get("comp_earnings", 0)
            logs['total_o_salarial_earnings'] = data_payslip.get(
                "o_salarial_earnings", 0)
            logs['total_o_rights'] = data_payslip.get("o_rights", 0)
            logs['total_o_earnings'] = data_payslip.get("o_earnings", 0)
            logs['ibd'] = ibd
            logs['rate'] = rate * 100
            logs['total_base'] = ibd
            logs['total'] = prov_vac_total

            return {
                'name': self.name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': ibd,
                'qty': 1,
                'rate': rate * 100,
                'total': prov_vac_total,
                'origin': 'local',
                'concept_id': self.id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
                'log_ids': logs,
            }

        date_to = data_payslip['period'].end
        if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date:
            date_to = data_payslip['contract'].settlement_date

        if not data_payslip['politics']['hr_payroll_co.total_avg_holidays']:
            self.get_last_year_prv_vac(data_payslip, date_to, True, logs)
            average = data_payslip['last_year_prv']['average_prv']
        else:
            self.get_last_year_holidays(data_payslip, date_to, True, logs)
            average = data_payslip['last_year_vac']['average']
        if 'holiday_book' not in data_payslip:
            self.get_holiday_book(data_payslip, date_to)
        days_left = data_payslip['holiday_book']['days_left']

        # Discount current no pay days
        no_pay_days = len(self.env['hr.leave.line'].search([
            ('period_id', '=', data_payslip['period'].id),
            ('contract_id', '=', data_payslip['contract'].id),
            ('state', '=', 'validated'),
            ('leave_id.category_type', '=', 'NO_PAY')
        ]))
        current_days_left = -no_pay_days * 15 / \
            data_payslip['contract'].get_benefits_days_base()
        days_left += current_days_left

        logs['holidays_days_left'] = days_left
        logs['total'] = average * days_left

        total = (average * days_left)

        prv_vac_account = self._get_credit_account_concept(
            data_payslip['contract'])
        if not prv_vac_account:
            raise ValidationError('El concepto provisiones de '
                                  'vacaciones no tiene cuenta contable configurada.')
        partner_id = data_payslip['contract'].employee_id.partner_id

        prv_vac_previous = self.env['account.move.line'].search([
            ('account_id', '=', prv_vac_account.id),
            ('parent_state', '=', 'posted'),
            ('partner_id', '=', partner_id.id)])

        prv_vac_previous_amount = sum(
            [x.credit - x.debit for x in prv_vac_previous])

        total_previous = {}
        is_second_period = data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'SECOND'
        date_from_previous = data_payslip['period'].start.replace(
            day=1) if is_second_period else data_payslip['period'].start
        concepts_previuos = ('VAC_LIQ',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts_previuos)

        if sum(total_previous.values()):
            total = prv_vac_previous_amount * -1
        else:
            total -= prv_vac_previous_amount
            total = round(total)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': average,
            'qty': days_left,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _PROV_PRIMA_NAV(self, data_payslip):
        percentage = data_payslip.get('politics', {}).get(
            'hr_payroll_co.percentage_prv_nav', 0)
        rate = percentage / 100
    
        if not percentage:
            return

        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end

        if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date:
            date_to = data_payslip['contract'].settlement_date

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        wage = data_payslip['contract'].wage
        worked_days = days360(date_from, date_to)

        if not worked_days:
            return

        base = (wage / 30) * worked_days
        total = base * rate

        total_previous = {}
        concepts_previuos = ('PROV_PRIMA_NAV',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': date_to}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': (wage / 30) * worked_days,
            'qty': 1,
            'rate': percentage,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _PROV_DIA_31(self, data_payslip):
        percentage = data_payslip.get('politics', {}).get(
            'hr_payroll_co.percentage_prv_day_31', 0)
        
        rate = percentage / 100

        if not percentage:
            return

        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end

        if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date:
            date_to = data_payslip['contract'].settlement_date

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        wage = data_payslip['contract'].wage
        worked_days = days360(date_from, date_to)

        if not worked_days:
            return

        base = (wage / 30) * worked_days
        total = base * rate

        total_previous = {}
        concepts_previuos = ('PROV_DIA_31',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': date_to}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': (wage / 30) * worked_days,
            'qty': 1,
            'rate': percentage,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _PROV_AUX_VAC(self, data_payslip):
        percentage = data_payslip.get('politics', {}).get(
            'hr_payroll_co.percentage_prv_aux_vac', 0)

        rate = percentage / 100

        if not percentage:
            return

        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end

        if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date:
            date_to = data_payslip['contract'].settlement_date

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        wage = data_payslip['contract'].wage
        worked_days = days360(date_from, date_to)

        if not worked_days:
            return

        base = (wage / 30) * worked_days
        total = base * rate

        total_previous = {}
        concepts_previuos = ('PROV_AUX_VAC',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': date_to}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': (wage / 30) * worked_days,
            'qty': 1,
            'rate': percentage,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _PROV_ANT(self, data_payslip):
        percentage = data_payslip.get('politics', {}).get(
            'hr_payroll_co.percentage_prv_old', 0)

        rate = percentage / 100

        if not percentage:
            return

        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end

        if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date:
            date_to = data_payslip['contract'].settlement_date

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        wage = data_payslip['contract'].wage
        worked_days = days360(date_from, date_to)

        if not worked_days:
            return

        base = (wage / 30) * worked_days
        total = base * rate

        total_previous = {}
        concepts_previuos = ('PROV_ANT',)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': date_to}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': (wage / 30) * worked_days,
            'qty': 1,
            'rate': percentage,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }
