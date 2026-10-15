# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.addons.utilities_collection import orm
from odoo.addons.utilities_collection.time import days360
from dateutil.relativedelta import relativedelta

CONCEPTS_GT = ['BASICO_GT', 'IGSS',
               'AGUINALDO_GT', 'AGUINALDO_GT_PART', 'AGUINALDO_GT_LIQ',
               'BONO_14', 'BONO_14_PART', 'BONO_14_LIQ',
               'VAC_GT', 'VAC_LIQ_GT','INDEM_GT',
               'NETO_GT', 'NETO_LIQ_GT',
               'PRV_AGU_GT', 'PRV_BON_14', 'PRV_VAC_GT', 'PRV_IND_GT', 'PRV_CUO_PAT']

TPCT = 'total_previous_categories'
TPCP = 'total_previous_concepts'

class HrConcept(models.Model):
    _inherit = 'hr.concept'

    ############################################################################
    # ------------------- CALCULO DE CONCEPTOS INDIVIDUALES GT ----------------#
    ############################################################################

    def _BASICO_GT(self, data_payslip):
        assumed_disability_february = data_payslip['politics']['hr_payroll_gt.assumed_disability_february_gt']
        def get_detail():
            rate = 1

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
                ('leave_id.category_type', 'in', ('MAT_LIC', 'PAT_LIC')),
            ], order='date desc', limit=1)

            wage = 0
            days = 0
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

                wage += current_wage.wage / 30 * rate
                days += 1

            check_period = data_payslip['period'].type_biweekly == 'SECOND' or data_payslip['period'].type_period == 'MONTHLY'
            fix_febrary_days = data_payslip['period'].end.month == 2 and check_period and (
                not settlement_date or settlement_date > data_payslip['period'].end)
            if check_period and data_payslip['period'].end.month == 2 and settlement_date:
                next_date = settlement_date + relativedelta(days=1)
                if next_date.month == 3 and settlement_date.month == 2:
                    fix_febrary_days = True
            if fix_febrary_days:
                current_wage = max(filter(lambda x: x.date <= data_payslip['period'].end, wage_history),
                                   key=lambda x: x.date)
                days_to_add = 2 if data_payslip['period'].end.day == 28 else 1
                if (assumed_disability_february and data_payslip['period'].end.month == 2
                        and data_payslip['period'].end.day == leave.date.day
                        and leave.leave_id.category_type in ('MAT_LIC', 'PAT_LIC')):
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

            return wage, days, rate

        wage, days, rate = get_detail()

        data_payslip['BASICO_GT'] = (wage, days)
        data_payslip['wage'] = wage
        return {
            'name': self.name,
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

    def _IGSS(self, data_payslip):
        if 'IBD' not in data_payslip:
            self._compute_ibd_gt(data_payslip)
        rate = data_payslip['politics']['hr_payroll_gt.percentage_igss']
        total = data_payslip['IBD'] * rate / 100
        total -= data_payslip.get(TPCP, {}).get('IGSS', 0)

        total_previous = {}
        date_from_previous = data_payslip['period'].start.replace(day=1)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('IGSS',))

        data_payslip['IGSS'] = total - total_previous.get('IGSS', 0.0)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['IBD'],
            'qty': 1,
            'rate': rate,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _BONO_14(self, data_payslip):
        if data_payslip['period'].start.month != 7:
            return

        date_from = (data_payslip['period'].start - relativedelta(years=1)).replace(month=7, day=1)
        date_to = data_payslip['period'].start.replace(month=6, day=30)
        logs = {}
        total_previous = {}

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        base, qty, total = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to, True, logs)

        concepts_previuos = ('BONO_14', 'BONO_14_LIQ', 'BONO_14_PART')

        date_from_previous = date_from.replace(month=8)

        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())
        logs['total'] = total
        data_payslip['BONO_14'] = total

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

    def _BONO_14_PART(self, data_payslip):
        if data_payslip['period'].start.month >= 7 and data_payslip['period'].start.month <= 12:
            date_from = data_payslip['period'].start.replace(month=7, day=1)
        else:
            date_from = (data_payslip['period'].start - relativedelta(years=1)).replace(month=7, day=1)
        date_to = data_payslip['period'].end
        logs = {}
        total_previous = {}

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        base, qty, total = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to, True, logs)

        concepts_previuos = ('BONO_14', 'BONO_14_LIQ', 'BONO_14_PART')

        date_from_previous = date_from.replace(month=8)

        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())
        logs['total'] = total
        data_payslip['BONO_14_PART'] = total

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

    def _BONO_14_LIQ(self, data_payslip):
        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        if data_payslip['period'].start.month >= 7 and data_payslip['period'].start.month <= 12:
            date_from = data_payslip['period'].start.replace(month=7, day=1)
        else:
            date_from = (data_payslip['period'].start - relativedelta(years=1)).replace(month=7, day=1)
        date_to = data_payslip['contract'].settlement_date
        logs = {}
        total_previous = {}

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        base, qty, total = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to, True, logs)

        concepts_previuos = ('BONO_14', 'BONO_14_LIQ', 'BONO_14_PART')

        date_from_previous = date_from.replace(month=8)

        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())
        logs['total'] = total
        data_payslip['BONO_14'] = total

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

    def _AGUINALDO_GT(self, data_payslip):
        if data_payslip['period'].start.month != 12:
            return

        date_from = (data_payslip['period'].start - relativedelta(years=1)).replace(month=12, day=1)
        date_to = data_payslip['period'].start.replace(month=11, day=30)
        logs = {}
        total_previous = {}

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        base, qty, total = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to, True, logs)

        concepts_previuos = ('AGUINALDO_GT', 'AGUINALDO_GT_LIQ', 'AGUINALDO_GT_PART')

        date_from_previous = (data_payslip['period'].start).replace(month=1, day=1)

        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())
        logs['total'] = total
        data_payslip['BONO_14'] = total

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

    def _AGUINALDO_GT_PART(self, data_payslip):
        date_from = (data_payslip['period'].start - relativedelta(years=1)).replace(month=12, day=1)
        date_to = data_payslip['period'].end
        logs = {}
        total_previous = {}

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        base, qty, total = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to, True, logs)

        concepts_previuos = ('AGUINALDO_GT', 'AGUINALDO_GT_LIQ', 'AGUINALDO_GT_PART')

        date_from_previous = (data_payslip['period'].start).replace(month=1, day=1)

        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts_previuos)
        
        total -= sum(total_previous.values())
        logs['total'] = total
        data_payslip['BONO_14'] = total

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

    def _AGUINALDO_GT_LIQ(self, data_payslip):
        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        if data_payslip['period'].start.month == 12:
            date_from = data_payslip['period'].start
        else:
            date_from = (data_payslip['period'].start - relativedelta(years=1)).replace(month=12, day=1)
        date_to = data_payslip['contract'].settlement_date
        logs = {}
        total_previous = {}

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        base, qty, total = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to, True, logs)

        concepts_previuos = ('AGUINALDO_GT', 'AGUINALDO_GT_LIQ', 'AGUINALDO_GT_PART')

        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts_previuos)

        total -= sum(total_previous.values())
        logs['total'] = total
        data_payslip['AGUINALDO_GT_LIQ'] = total

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

    def _PRV_AGU_GT(self, data_payslip):
        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end
        rate = data_payslip['politics']['hr_payroll_gt.rate_prv_agu_gt']

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        
        base, qty = self._compute_base_prv(data_payslip, date_from, date_to)

        total_previous = {}
        date_from_previous = data_payslip['period'].start.replace(day=1)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRV_AGU_GT',))

        base -= total_previous.get('PRV_AGU_GT', 0.0)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': rate,
            'total': base * (rate / 100),
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None
        }

    def _PRV_BON_14(self, data_payslip):
        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end
        rate = data_payslip['politics']['hr_payroll_gt.rate_prv_bon_14']

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        
        base, qty = self._compute_base_prv(data_payslip, date_from, date_to)

        total_previous = {}
        date_from_previous = data_payslip['period'].start.replace(day=1)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRV_BON_14',))

        base -= total_previous.get('PRV_BON_14', 0.0)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': rate,
            'total': base * (rate / 100),
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None
        }

    def _PRV_VAC_GT(self, data_payslip):
        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end
        rate = data_payslip['politics']['hr_payroll_gt.rate_prv_vac_gt']

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        
        base, qty = self._compute_base_prv(data_payslip, date_from, date_to)

        total_previous = {}
        date_from_previous = data_payslip['period'].start.replace(day=1)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRV_VAC_GT',))

        base -= total_previous.get('PRV_VAC_GT', 0.0)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': rate,
            'total': base * (rate / 100),
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None
        }

    def _PRV_IND_GT(self, data_payslip):
        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end
        rate = data_payslip['politics']['hr_payroll_gt.rate_prv_ind_gt']

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        
        base, qty = self._compute_base_prv(data_payslip, date_from, date_to)

        total_previous = {}
        date_from_previous = data_payslip['period'].start.replace(day=1)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRV_IND_GT',))

        base -= total_previous.get('PRV_IND_GT', 0.0)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': rate,
            'total': base * (rate / 100),
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None
        }

    def _PRV_CUO_PAT(self, data_payslip):
        date_from = data_payslip['period'].start.replace(day=1)
        date_to = data_payslip['period'].end
        rate = data_payslip['politics']['hr_payroll_gt.rate_prv_cuo_pat']

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        
        base, qty = self._compute_base_prv(data_payslip, date_from, date_to)

        total_previous = {}
        date_from_previous = data_payslip['period'].start.replace(day=1)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('PRV_CUO_PAT',))

        base -= total_previous.get('PRV_CUO_PAT', 0.0)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': rate,
            'total': base * (rate / 100),
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None
        }

    def _VAC_GT(self, data_payslip):
        date_from = data_payslip['contract'].date_start
        date_to = data_payslip['period'].end

        base, qty, total = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to)
        
        days_worked = (15 / 360) * qty
        total = (base / 360) * days_worked

        total_previous = {}
        is_second_period = data_payslip['period'].type_period == 'BIWEEKLY' and data_payslip['period'].type_biweekly == 'SECOND'
        date_from_previous = data_payslip['period'].start.replace(
            day=1) if is_second_period else data_payslip['period'].start
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('VAC_GT',))

        total -= total_previous.get('VAC_GT', 0)

        data_payslip['VAC_GT'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': days_worked,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None
        }

    def _VAC_LIQ_GT(self, data_payslip):
        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        date_from = data_payslip['contract'].date_start
        date_to = data_payslip['contract'].settlement_date

        base, qty, total = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to)
        
        days_worked = (15 / 360) * qty
        total = (base / 360) * days_worked

        total_previous = {}

        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from, 'end': data_payslip['period'].end}, data_payslip['contract'].id, ('VAC_LIQ_GT','VAC_GT'))

        total -= total_previous.get('VAC_LIQ_GT', 0)

        data_payslip['VAC_LIQ_GT'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': days_worked,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None
        }

    def _INDEM_GT(self, data_payslip):
        if data_payslip['contract'].settlement_type not in ['n_causa', 'unil']:
            return
        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        date_to = data_payslip['contract'].settlement_date
        date_from = (date_to - relativedelta(months=6)) + relativedelta(days=1)

        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        base, days, amount = self._compute_social_benefits_gt(
            data_payslip, date_from, date_to)

        days_worked = days360(data_payslip['contract'].date_start, date_to)

        base = (base / days) * 30
    
        base += (data_payslip['contract'].wage / 12) * 2

        total = (base * days_worked) / 365
        
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': days_worked,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None
        }

    def _NETO_GT(self, data_payslip):
        total_earnings = ['earnings', 'o_salarial_earnings',
                          'comp_earnings', 'o_rights', 'o_earnings', 'non_taxed_earnings']
        total_deductions = ['deductions']
        total = 0
        for te in total_earnings:
            total += round(data_payslip.get(te, 0), 2)
        for td in total_deductions:
            total -= round(data_payslip.get(td, 0), 2)

        ces_codes = ['CES']
        total -= sum([round(data_payslip.get(code, 0), 2) for code in ces_codes])
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': total,
            'qty': 1,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _NETO_LIQ_GT(self, data_payslip):
        total_earnings = ['earnings', 'o_salarial_earnings',
                          'comp_earnings', 'o_rights', 'o_earnings', 'non_taxed_earnings']
        total_deductions = ['deductions']
        total = 0
        for te in total_earnings:
            total += round(data_payslip.get(te, 0), 2)
        for td in total_deductions:
            total -= round(data_payslip.get(td, 0), 2)

        ces_codes = ['CES']
        total -= sum([round(data_payslip.get(code, 0), 2) for code in ces_codes])
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': total,
            'qty': 1,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    ############################################################################
    # ------------------- METODOS PARA CALCULOS                ----------------#
    ############################################################################

    def _compute_ibd_gt(self, data_payslip):
        salary = 0
        total_previous = {}
        categories = ('earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights')
        for category in categories:
            salary += data_payslip.get(TPCT, {}).get(category, 0)
            salary += data_payslip.get(category, 0)
        
        self._get_total_concept_categories(data_payslip['cr'],
            total_previous,
            {'start': data_payslip['period'].start.replace(day=1), 'end': data_payslip['period'].end},
            data_payslip['contract'].id,
            exclude=('BASICO',), categories=categories)
        
        salary += sum(total_previous.values())

        domain = [('state', 'in', ('paid', 'validated')),
                  ('period_id.start', '>=', data_payslip['period'].start.replace(day=1)),
                  ('period_id.end', '<=', data_payslip['period'].end),
                  ('contract_id', '=', data_payslip['contract'].id),
                  ('leave_id.category_type', '=', 'VAC_MONEY'),
                  ('leave_id.leave_type_id.id', 'in', data_payslip['payslip_type_id'].leave_types_ids.ids)]
        vac_money_amount = sum(
            self.env['hr.leave.line'].search(domain).mapped('amount'))
        salary -= vac_money_amount
        
        data_payslip['IBD'] = salary 

    def get_seq_concept_category_gt(self):
        for i, concept in enumerate(CONCEPTS_GT):
            if concept == self.code:
                return i
        return len(CONCEPTS_GT)

    def _compute_social_benefits_gt(self, data_payslip, date_from, date_to, audit=False, log={}):
        leave_line = self.env['hr.leave.line']
        data_base = {}
        data_base['salary'] = 0

        months_salaries = data_payslip['contract'].average_wage_history_by_days(
            date_from, date_to)
        if months_salaries:
            for salary in months_salaries.values():
                data_base['salary'] += sum(salary.values())
        
        if self.code in ('VAC_GT', 'VAC_LIQ_GT'):
            actual_variable = self._get_actual_variable_salary(data_payslip)
            data_base['variable'] = actual_variable

        base = sum(data_base.values())

        days_worked = days360(date_from, date_to)
        days_not_worked = leave_line.get_days_not_worked(
            data_payslip['contract'], date_from, date_to, False, data_payslip, False)
        days_worked -= days_not_worked

        total = (base / 360) * 30

        return base, days_worked, total

    def _compute_base_prv(self, data_payslip, date_from, date_to, audit=False, log={}):
        leave_line = self.env['hr.leave.line']
        data_base = {}
        data_base['salary'] = 0

        months_salaries = data_payslip['contract'].average_wage_history_by_days(
            date_from, date_to)
        if months_salaries:
            for month in months_salaries.values():
                data_base['salary'] += sum(month.values())
        
        if self.code in ('PRV_CUO_PAT', 'PRV_VAC_GT'):
            actual_variable = self._get_actual_variable_salary(data_payslip)
        else:
            actual_variable = self._get_actual_comp_earnings(data_payslip)

        data_base['variable'] = actual_variable
        base = sum(data_base.values())

        days_worked = days360(date_from, date_to)
        days_not_worked = leave_line.get_days_not_worked(
            data_payslip['contract'], date_from, date_to, False, data_payslip, False)
        days_worked -= days_not_worked

        return base, days_worked

    def _get_actual_comp_earnings(self, data_payslip):
        categories = ('earnings', 'o_salarial_earnings')
        conv_cat = ('PRIMA_LIQ_CONV', 'PRIMA_VAC_CONV')
        sum_categories = sum([data_payslip.get(con, 0) for con in categories])
        sum_conv = sum([data_payslip.get(con, 0) for con in conv_cat])
        wage = 0
        if 'wage' in data_payslip:
            wage = data_payslip.get('wage')
            if type(wage) == dict:
                wage = wage.get('wage', 0)
        variable_salary = sum_categories - wage - sum_conv
        return variable_salary if variable_salary > 0 else 0
