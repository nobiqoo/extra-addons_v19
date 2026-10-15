# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.utilities_collection import orm
from odoo.addons.hr_payroll_co.models.hr_concept.hr_concept_base import TPCP, TPCT


class HrConcept(models.Model):
    _inherit = 'hr.concept'

    def _compute_brtf(self, data_payslip):
        logs = {}
        total_previous = {}
        total_income = 0

        period = {
            'start': data_payslip['period'].start,
            'end': data_payslip['period'].end
        }

        self._get_total_concept_categories(data_payslip['cr'], total_previous, period, data_payslip['contract'].id,
                                           exclude=('BASICO', 'PRIMA_CONV'), categories=('o_rights',))

        for category in ['earnings', 'o_earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']:
            current_total = data_payslip.get(TPCT, {}).get(category, 0)
            current_total += data_payslip.get(category, 0)

            logs[category] = current_total
            total_income += current_total

        logs['o_rights'] += total_previous.get('o_rights', 0)

        logs['income_ext'] = data_payslip.get('income_EXT', 0)
        total_income -= data_payslip.get('income_EXT', 0)

        logs['apply_procedure_2'] = data_payslip['contract'].apply_procedure_2

        if data_payslip['contract'].apply_procedure_2:
            for concept in ['PRIMA', 'PRIMA_LIQ']:
                # La prima del recibo actual ya está incluida en el total por
                # categoría (o_rights). Aquí solo se agrega la prima del mes
                # pagada en OTROS recibos (TPCP), que TPCT excluye. Sumar
                # data_payslip.get(concept, 0) la contaría dos veces.
                current_total = data_payslip.get(TPCP, {}).get(concept, 0)

                logs[concept] = current_total
                total_income += current_total
        else:
            for concept in ['PRIMA', 'PRIMA_LIQ']:
                current_total = data_payslip.get(concept, 0)

                logs[concept] = -current_total
                total_income -= current_total

        logs['total_income'] = total_income

        # Deducciones no constitutivas de ingreso
        total_nci = 0
        for nci in ['DED_PENS', 'DED_EPS', 'FOND_SOL', 'FOND_SUB', 'DED_PENS_PUBLIC', 'DED_PENS_ACCAI']:
            current_total = data_payslip.get(TPCP, {}).get(nci, 0)
            current_total += data_payslip.get(nci, 0)

            logs[nci] = current_total
            total_nci += current_total

        logs['total_nci'] = total_nci

        neto_income = total_income - total_nci
        logs['neto_income'] = neto_income
        if neto_income == 0:
            data_payslip['BRTF'] = 0
            data_payslip['PRV_BRTF_25P'] = 0
            data_payslip['PRV_BRTF_40P'] = 0
            return

        uvt = data_payslip['economic_variables']['UVT'][data_payslip['current_year_month']]
        uvt_qty_to_top25 = data_payslip['economic_variables']['ANNUAL_LIMIT_25P'][data_payslip['current_year_month']]
        uvt_qty_to_top40 = data_payslip['economic_variables']['ANNUAL_LIMIT_40P'][data_payslip['current_year_month']]

        logs['current_year'] = data_payslip['period'].start.year
        logs['uvt'] = uvt

        # Deducciones
        if data_payslip['contract'].deduction_dependents:
            deduction_base = total_income * 0.1
            deduction_dependents = deduction_base if deduction_base <= 32 * uvt else 32 * uvt
        else:
            deduction_dependents = 0

        if data_payslip['contract'].deduction_by_estate <= 100 * uvt:
            deduction_estate = data_payslip['contract'].deduction_by_estate
        else:
            deduction_estate = 100 * uvt

        if data_payslip['contract'].deduction_by_healthcare <= 16 * uvt:
            deduction_healthcare = data_payslip['contract'].deduction_by_healthcare
        else:
            deduction_healthcare = 16 * uvt

        if data_payslip['contract'].deduction_by_icetex <= 8.333 * uvt:
            deduction_icetex = data_payslip['contract'].deduction_by_icetex
        else:
            deduction_icetex = 8.333 * uvt

        deduction_total = deduction_dependents + deduction_estate + \
            deduction_healthcare + deduction_icetex

        logs['deduction_dependents'] = deduction_dependents
        logs['deduction_estate'] = deduction_estate
        logs['deduction_healthcare'] = deduction_healthcare
        logs['deduction_icetex'] = deduction_icetex
        logs['deduction_total'] = deduction_total

        # Deducciones voluntarias
        AVP = data_payslip.get('outcome_AVP', 0)
        AFC = data_payslip.get('outcome_AFC', 0)

        query = '''
        SELECT 
            CASE 
                WHEN HNT.category = 'deductions' THEN 'outcome' || '_' || HNT.modality
                ELSE 'income' || '_' || HNT.modality
            END,
            HNL.amount
        FROM hr_novelty_line AS HNL
        INNER JOIN hr_novelty AS HN
            ON HN.id = HNL.novelty_id
        INNER JOIN hr_novelty_type AS HNT
            ON HNT.id = HN.novelty_type_id
        INNER JOIN hr_period AS PP 
            ON PP.id = HNL.period_id
        WHERE 
            PP.start < %(end)s AND  PP.end > %(start)s
            AND HN.contract_id = %(contract_id)s
            AND HNL.state = 'paid'
            AND (HNT.modality IS NOT NULL OR HNT.modality != '')
        '''
        param = {
            'contract_id': data_payslip['contract'].id,
            'start': data_payslip['period'].start.replace(day=1),
            'end': data_payslip['period'].end,
        }
        data = orm._fetchall(self._cr, query, param)

        AVP_previous = sum([x[1] for x in data if x[0] == 'outcome_AVP'])
        AFC_previous = sum([x[1] for x in data if x[0] == 'outcome_AFC'])

        voluntary_contributions = AVP + AFC + AVP_previous + AFC_previous
        if voluntary_contributions > neto_income * 0.3:
            voluntary_contributions = neto_income * 0.3

        logs['avp'] = AVP + AVP_previous
        logs['afc'] = AFC + AFC_previous
        logs['voluntary_contributions'] = voluntary_contributions

        # Provisions concepts
        concepts = ('PRV_BRTF_25P', 'PRV_BRTF_40P')

        # Provisions paid in period
        prv_paid = {}
        date_from_previous = data_payslip['period'].start.replace(day=1)
        self._get_total_concepts(
            data_payslip['cr'], prv_paid, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts)

        total_previous = {}
        date_from_previous = data_payslip['period'].start.replace(
            month=1, day=1)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts)

        prov_top25 = total_previous.get('PRV_BRTF_25P', 0)
        annual_top25 = uvt_qty_to_top25 * uvt
        logs['annual_top25'] = annual_top25
        max_monthly_top25 = annual_top25 - prov_top25

        monthly_top25 = (neto_income - deduction_total -
                         voluntary_contributions) * 0.25
        if monthly_top25 > max_monthly_top25:
            monthly_top25 = max_monthly_top25

        total_top25 = prov_top25 + monthly_top25
        top25 = monthly_top25 if total_top25 <= annual_top25 else 0
        logs['top25_monthly'] = top25
        logs['top25_total'] = total_top25

        prov_top40 = total_previous.get('PRV_BRTF_40P', 0)
        annual_top40 = uvt_qty_to_top40 * uvt
        logs['annual_top40'] = annual_top40
        max_monthly_top40 = annual_top40 - prov_top40

        exempt_rent = deduction_total + voluntary_contributions + top25

        accumulated_minimum_top_40 = data_payslip['politics']['hr_payroll_co.accumulated_minimum_top_40']
        if accumulated_minimum_top_40:
            monthly_top40 = exempt_rent
        else:
            monthly_top40 = neto_income * 0.4

        if monthly_top40 > max_monthly_top40:
            monthly_top40 = max_monthly_top40

        total_top40 = prov_top40 + monthly_top40
        top40 = monthly_top40 if total_top40 <= annual_top40 else 0
        logs['top40_monthly'] = top40
        logs['top40_total'] = total_top40

        if exempt_rent > top40:
            exempt_rent = top40

        data_payslip['BRTF'] = neto_income - exempt_rent
        data_payslip['PRV_BRTF_25P'] = top25 - prv_paid.get('PRV_BRTF_25P', 0)
        data_payslip['PRV_BRTF_40P'] = top40 - prv_paid.get('PRV_BRTF_40P', 0)

        logs['exempt_rent'] = exempt_rent
        logs['BRTF'] = data_payslip['BRTF']
        data_payslip['BRTF_logs'] = logs

    def _RTEFTE(self, data_payslip):
        if data_payslip['contract'].fiscal_type_id.code == '12':
            return

        if 'BRTF' not in data_payslip:
            self._compute_brtf(data_payslip)

        if data_payslip['BRTF'] == 0:
            return

        previous = data_payslip.get(TPCP, {}).get('RTEFTE', 0)
        if data_payslip['contract'].apply_procedure_2:
            rate = data_payslip['contract'].withholding_percent
        else:
            rate = self._get_rate_trtefte(data_payslip, data_payslip['BRTF'])

        if rate == 0 and previous == 0:
            return

        total = data_payslip['BRTF'] * rate / 100 - previous

        date_to = data_payslip['contract'].settlement_date or data_payslip['period'].end
        contract_duration = date_to - data_payslip['contract'].date_start
        contract_duration = contract_duration.days

        contract_start = data_payslip['contract'].date_start
        period_start = data_payslip['period'].start
        wage_date = contract_start if contract_start > period_start else period_start

        logs = self._initialize_logs(data_payslip)
        logs.update({
            'date_from': data_payslip['contract'].date_start,
            'date_to': data_payslip['contract'].settlement_date or None,
            'total_salary': data_payslip['contract'].get_wage(wage_date).get('wage', 0),
            'total_earnings': data_payslip['BRTF_logs'].get('earnings', 0),
            'total_o_earnings': data_payslip['BRTF_logs'].get('o_earnings', 0),
            'total_o_salarial_earnings': data_payslip['BRTF_logs'].get('o_salarial_earnings', 0),
            'total_comp_earnings': data_payslip['BRTF_logs'].get('comp_earnings', 0),
            'total_o_rights': data_payslip['BRTF_logs'].get('o_rights', 0),
            'total_base': data_payslip['BRTF'],
            'total': total,
            'contract_duration': contract_duration,
            'rate': rate,

            'rtefte_income_ext': data_payslip['BRTF_logs'].get('income_ext'),
            'rtefte_apply_procedure_2': data_payslip['BRTF_logs'].get('apply_procedure_2'),
            'rtefte_prima': data_payslip['BRTF_logs'].get('prima'),
            'rtefte_prima_liq': data_payslip['BRTF_logs'].get('prima_liq'),
            'rtefte_total_income': data_payslip['BRTF_logs'].get('total_income'),
            'rtefte_ded_pens': sum([data_payslip['BRTF_logs'].get(code, 0) for code in ('DED_PENS', 'DED_PENS_PUBLIC', 'DED_PENS_ACCAI')]),
            'rtefte_ded_eps': data_payslip['BRTF_logs'].get('DED_EPS'),
            'rtefte_fond_sol': data_payslip['BRTF_logs'].get('FOND_SOL'),
            'rtefte_fond_sub': data_payslip['BRTF_logs'].get('FOND_SUB'),
            'rtefte_total_nci': data_payslip['BRTF_logs'].get('total_nci'),
            'rtefte_neto_income': data_payslip['BRTF_logs'].get('neto_income'),
            'rtefte_current_year': data_payslip['BRTF_logs'].get('current_year'),
            'rtefte_uvt': data_payslip['BRTF_logs'].get('uvt'),
            'rtefte_deduction_dependents': data_payslip['BRTF_logs'].get('deduction_dependents'),
            'rtefte_deduction_estate': data_payslip['BRTF_logs'].get('deduction_estate'),
            'rtefte_deduction_healthcare': data_payslip['BRTF_logs'].get('deduction_healthcare'),
            'rtefte_deduction_icetex': data_payslip['BRTF_logs'].get('deduction_icetex'),
            'rtefte_deduction_total': data_payslip['BRTF_logs'].get('deduction_total'),
            'rtefte_avp': data_payslip['BRTF_logs'].get('avp'),
            'rtefte_afc': data_payslip['BRTF_logs'].get('afc'),
            'rtefte_voluntary_contributions': data_payslip['BRTF_logs'].get('voluntary_contributions'),
            'rtefte_annual_top25': data_payslip['BRTF_logs'].get('annual_top25'),
            'rtefte_top25_monthly': data_payslip['BRTF_logs'].get('top25_monthly'),
            'rtefte_top25_total': data_payslip['BRTF_logs'].get('top25_total'),
            'rtefte_annual_top40': data_payslip['BRTF_logs'].get('annual_top40'),
            'rtefte_top40_monthly': data_payslip['BRTF_logs'].get('top40_monthly'),
            'rtefte_top40_total': data_payslip['BRTF_logs'].get('top40_total'),
            'rtefte_exempt_rent': data_payslip['BRTF_logs'].get('exempt_rent'),
        })

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['BRTF'],
            'qty': 1,
            'rate': rate,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _BRTF(self, data_payslip):
        if data_payslip['contract'].fiscal_type_id.code == '12':
            return
        if 'BRTF' not in data_payslip:
            self._compute_brtf(data_payslip)
        if data_payslip['BRTF'] == 0:
            return
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['BRTF'],
            'qty': 1,
            'rate': 100,
            'total': data_payslip['BRTF'],
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _PRV_BRTF_25P(self, data_payslip):
        if data_payslip['contract'].contract_type_id.type_class == 'apr':
            return
        if 'PRV_BRTF_25P' not in data_payslip:
            self._compute_brtf(data_payslip)
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['PRV_BRTF_25P'],
            'qty': 1,
            'rate': 100,
            'total': data_payslip['PRV_BRTF_25P'],
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _PRV_BRTF_40P(self, data_payslip):
        if data_payslip['contract'].contract_type_id.type_class == 'apr':
            return
        if 'PRV_BRTF_40P' not in data_payslip:
            self._compute_brtf(data_payslip)
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['PRV_BRTF_40P'],
            'qty': 1,
            'rate': 100,
            'total': data_payslip['PRV_BRTF_40P'],
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _BRTF_PRIMA(self, data_payslip):
        if data_payslip['contract'].fiscal_type_id.code == '12' or data_payslip['contract'].apply_procedure_2:
            return

        total_prima = 0

        for concept_code in ('PRIMA', 'PRIMA_LIQ'):
            total_prima += data_payslip.get(TPCP, {}).get(concept_code, 0)
            total_prima += data_payslip.get(concept_code, 0)

        concepts = ('BRTF_PRIMA',)
        total_previous = {}
        period_start = data_payslip['period'].start
        semester_start_month = 1 if period_start.month <= 6 else 7
        date_from_previous = period_start.replace(
            month=semester_start_month, day=1)
        self._get_total_concepts(
            data_payslip['cr'], total_previous, {'start': date_from_previous, 'end': data_payslip['period'].end}, data_payslip['contract'].id, concepts)

        prv_brtf_prima = total_previous.get('BRTF_PRIMA', 0)

        total_prima -= prv_brtf_prima

        if total_prima == 0:
            data_payslip['BRTF_PRIMA'] = 0
            return
        
        exempt_rent = total_prima * 0.25
        total = total_prima - exempt_rent

        data_payslip['BRTF_PRIMA'] = total
        
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

    def _RTF_PRIMA(self, data_payslip):
        if data_payslip['contract'].fiscal_type_id.code == '12' or data_payslip['contract'].apply_procedure_2:
            return

        total_prima = data_payslip.get('BRTF_PRIMA', 0)

        if total_prima == 0:
            return

        rate = self._get_rate_trtefte(data_payslip, total_prima)

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': total_prima,
            'qty': 1,
            'rate': rate,
            'total': total_prima * rate / 100,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }
