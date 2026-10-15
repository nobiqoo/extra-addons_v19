# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import ValidationError
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.addons.utilities_collection import orm
from datetime import date
from odoo.addons.utilities_collection.time import days360


TEACHING_PHASE = 'teaching_phase'
PRODUCTIVE_PHASE = 'productive_phase'


class HrConcept(models.Model):
    _inherit = 'hr.concept'

    def _BASICO(self, data_payslip):
        assumed_disability_february = data_payslip['politics']['hr_payroll_co.assumed_disability_february']

        def get_detail():
            settlement_date = data_payslip['contract'].settlement_date
            period_days = data_payslip['period'].get_days()
            wage_history = self.env['wage.update.history'].search([
                ('contract_id', '=', data_payslip['contract'].id),
                ('date', '<=', data_payslip['period'].end)
            ])

            leave_days = (
                # Leave to paid in current payslip
                [d['day'] for d in data_payslip['payslip_days'] if d['day_type'] == 'A'] +

                # Leave already paid in period
                [l.date.day for l in self.env['hr.leave.line'].search([
                    ('contract_id', '=', data_payslip['contract'].id),
                    ('state', '=', 'paid'),
                    ('date', '>=', data_payslip['period'].start),
                    ('date', '<=', data_payslip['period'].end),
                    ('leave_id.category_type', '!=', 'VAC_MONEY'),
                ])]
            )

            leave = self.env['hr.leave.line'].search([
                ('contract_id', '=', data_payslip['contract'].id),
                ('state', '=', 'validated'),
                ('date', '>=', data_payslip['period'].start),
                ('date', '<=', data_payslip['period'].end),
                ('leave_id.category_type', 'in', ('MAT_LIC', 'PAT_LIC', 'SICKNESS')),
            ], order='date desc', limit=1)

            wage = 0
            days = 0
            rate = 0
            wage_no_base_ibc = 0

            for period_day in period_days:
                if period_day.day == 31:
                    continue

                if period_day.day in leave_days:
                    continue

                if period_day < data_payslip['contract'].date_start:
                    continue

                if settlement_date and period_day > settlement_date:
                    continue

                current_wage = max(filter(lambda x: x.date <= period_day, wage_history),
                                   key=lambda x: x.date)

                sena_phase = self.get_sena_phase(data_payslip, period_day)
                rate = self.wage_rate_by_contract_type(
                    data_payslip, sena_phase)

                daily_wage = current_wage.wage / 30 * rate
                wage += daily_wage
                if sena_phase == TEACHING_PHASE:
                    wage_no_base_ibc += daily_wage

                days += 1

            check_period = data_payslip['period'].type_biweekly == 'SECOND' or data_payslip['period'].type_period == 'MONTHLY'
            fix_febrary_days = data_payslip['period'].end.month == 2 and check_period and (
                not settlement_date or settlement_date > data_payslip['period'].end)
            if check_period and data_payslip['period'].end.month == 2 and settlement_date:
                next_date = settlement_date + relativedelta(days=1)
                if next_date.month == 3 and settlement_date.month == 2:
                    fix_febrary_days = True
            if fix_febrary_days:
                if rate == 0:
                    sena_phase = self.get_sena_phase(data_payslip, data_payslip['period'].end)
                    rate = self.wage_rate_by_contract_type(data_payslip, sena_phase)
                current_wage = max(filter(lambda x: x.date <= data_payslip['period'].end, wage_history),
                                   key=lambda x: x.date)
                days_to_add = 2 if data_payslip['period'].end.day == 28 else 1
                if (leave and assumed_disability_february and data_payslip['period'].end.month == 2
                        and data_payslip['period'].end.day == leave.date.day
                        and leave.leave_id.category_type in ('MAT_LIC', 'PAT_LIC', 'SICKNESS')):
                    if leave_days[-1] == data_payslip['period'].end.day:
                        days_to_add = 0
                wage += current_wage.wage / 30 * rate * days_to_add
                days += days_to_add

            rest_days_payable = data_payslip['contract'].get_rest_days_payable(
            )
            if rest_days_payable and days + rest_days_payable <= 30:
                current_wage = max(filter(lambda x: x.date <= data_payslip['period'].end, wage_history),
                                   key=lambda x: x.date)
                days += rest_days_payable
                wage += current_wage.wage / 30 * rate * rest_days_payable

            query = '''
                SELECT COALESCE(SUM(HPL.total), 0), COALESCE(SUM(HPL.qty), 0)            
                FROM hr_payslip_line AS HPL
                INNER JOIN hr_payslip AS HP
                    ON HP.id = HPL.payslip_id
                INNER JOIN hr_concept AS HC
                    ON HC.id = HPL.concept_id
                INNER JOIN hr_period AS PP
                    ON PP.id = HP.period_id
                WHERE 
                    HC.id = %(concept_id)s
                    AND HP.contract_id = %(contract_id)s
                    AND PP.start <= %(end)s
                    AND PP.end >= %(start)s
                    AND HP.state = 'paid'
                '''
            param = {
                'concept_id': self.id,
                'contract_id': data_payslip['contract'].id,
                'start': data_payslip['period'].start,
                'end': data_payslip['period'].end,
            }
            salary_paid = orm._fetchall(
                data_payslip['cr'], query, param)[0]

            wage -= salary_paid[0]
            days -= salary_paid[1]

            return wage, days, rate, wage_no_base_ibc

        wage, days, rate, wage_no_base_ibc = get_detail()
        type_class = data_payslip['contract'].contract_type_id.type_class
        if type_class == 'int':
            name = 'SUELDO BASICO INTEGRAL'
        elif type_class == 'apr':
            if data_payslip['contract'].fiscal_type_id.code == '12':
                name = 'CUOTA DE SOSTENIMIENTO LECTIVO'
            elif data_payslip['contract'].fiscal_type_id.code in ('19', '23'):
                name = 'CUOTA DE SOSTENIMIENTO PRODUCTIVO'
            else:
                raise ValidationError(
                    'Defina <Tipo de Cotizante> en el contrato y asegurese de que tenga código. Códigos validos 12 y 19')
        elif type_class == 'reg':
            name = self.name
        else:
            raise ValidationError(
                'No ha definido el tipo de contrato (Regular, Aprendiz o Integral).')

        data_payslip['BASICO'] = (wage, days)
        data_payslip['wage'] = wage
        data_payslip['wage_no_base_ibc'] = wage_no_base_ibc

        return {
            'name': name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': (wage / days) if days else 0,
            'qty': days,
            'rate': rate * 100,
            'total': wage,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def get_labor_reform_start_date(self):
        return date(2025, 7, 1)

    def _apply_labor_reform(self, data_payslip):
        if data_payslip['politics']['hr_payroll_co.dont_apply_labor_reform']:
            return False
        labor_reform_start_date = self.get_labor_reform_start_date()
        return data_payslip['period'].start >= labor_reform_start_date

    def get_sena_phase(self, data_payslip, date_ref):
        """
        Obtiene el tipo de fase para al aprendice sena
        """
        sena_phase = 'default'
        if data_payslip['contract'].fiscal_type_id.code == '12':
            sena_phase = TEACHING_PHASE
        if data_payslip['contract'].fiscal_type_id.code == '19':
            if not data_payslip['contract'].apprentice_to_worker_date:
                sena_phase = PRODUCTIVE_PHASE
            elif date_ref >= data_payslip['contract'].apprentice_to_worker_date:
                sena_phase = PRODUCTIVE_PHASE
            else:
                sena_phase = TEACHING_PHASE

        return sena_phase

    def wage_rate_by_contract_type(self, data_payslip, sena_phase):
        """
        Determina la tasa salarial según el tipo de contrato y fase del aprendiz SENA.
        En régimen tradicional (pre-reforma), la tasa depende de la tasa de desempleo del año anterior.
        """
        if self._apply_labor_reform(data_payslip):
            rates = {
                TEACHING_PHASE: 0.75,
                PRODUCTIVE_PHASE: 1,
                'default': 1,
            }
        else:
            a_year_ago = data_payslip['period'].end - relativedelta(years=1)
            year_month = (a_year_ago.year, a_year_ago.month)

            rates = {
                TEACHING_PHASE: 0.5,
                PRODUCTIVE_PHASE: 0.75 if data_payslip['economic_variables']['TSDES'][year_month] >= 10 else 1,
                'default': 1,
            }

        return rates[sena_phase]

    def _get_wage_in_teaching_phase(self, data_payslip):
        wage = 0
        contract_id = data_payslip['contract']

        if not self._apply_labor_reform(data_payslip):
            return wage

        if contract_id.fiscal_type_id.code != '19':
            return wage

        if not contract_id.apprentice_to_worker_date:
            return wage

        start_date = data_payslip['period'].start.replace(day=1)
        end_date = data_payslip['period'].end
        if data_payslip['contract'].date_start and data_payslip['contract'].date_start > start_date:
            start_date = data_payslip['contract'].date_start
        if data_payslip['contract'].settlement_date and data_payslip['contract'].settlement_date < end_date:
            end_date = data_payslip['contract'].settlement_date
        if not (start_date < contract_id.apprentice_to_worker_date < end_date):
            return wage

        year_month = (start_date.year, start_date.month)
        smmlv = data_payslip['economic_variables']['SMMLV'][year_month]

        rate = self.wage_rate_by_contract_type(data_payslip, TEACHING_PHASE)
        work_days_as_teaching = days360(
            start_date, contract_id.apprentice_to_worker_date) - 1
        wage = smmlv / 30 * work_days_as_teaching * rate

        return wage
