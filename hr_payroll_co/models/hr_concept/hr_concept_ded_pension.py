# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import ValidationError
from odoo.addons.hr_payroll_co.models.hr_concept.hr_concept_base import TPCP
from datetime import date


class HrConcept(models.Model):
    _inherit = 'hr.concept'

    def _build_payslip_line_for_ded_pens(self, data_payslip, value, total, rate):
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': value,
            'qty': 1,
            'rate': rate,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _is_valid_for_ded_pens(self, data_payslip):
        # Active employee retired
        if data_payslip['contract'].fiscal_subtype_id.code in ('01', '03', '04'):
            return False
        # No colombian laws
        if data_payslip['contract'].fiscal_type_id.code == '32':
            return False
        return True

    def _get_total_and_rate_for_ded_pens(self, data_payslip, value):
        rate = data_payslip['politics']['hr_payroll_co.pen_rate_employee']
        total = value * rate / 100

        return total, rate

    def _apply_pension_reform(self, data_payslip):
        """
        Aun no se debe aplicar los cambios de la reforma pensional entonces se comenta el codigo 

        pension_reform_start_date = date(2025, 7, 1)
        return data_payslip['period'].start >= pension_reform_start_date
        """
        return False

    def _DED_PENS(self, data_payslip):
        apply_pension_reform = self._apply_pension_reform(data_payslip)
        is_transitional_regime = data_payslip["contract"].is_transitional_regime
        if apply_pension_reform and not is_transitional_regime:
            return

        is_sena = data_payslip['contract'].contract_type_id.type_class == 'apr'
        if is_sena:
            if not self._apply_labor_reform(data_payslip):
                return

            if data_payslip['contract'].fiscal_type_id.code != '19':
                return

        if not self._is_valid_for_ded_pens(data_payslip):
            return

        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)

        value = data_payslip['IBD']
        if data_payslip['politics']['hr_payroll_co.assumed_pen_not_remunerate_licences']:
            no_pay_days = len(self.env['hr.leave.line'].search([
                ('date', '>=', data_payslip['period'].start.replace(day=1)),
                ('date', '<=', data_payslip['period'].end),
                ('contract_id', '=', data_payslip['contract'].id),
                ('state', 'in', ('validated', 'paid')),
                ('leave_id.category_type', '=', 'NO_PAY')
            ]))
            if no_pay_days:
                smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
                ibc_previous = data_payslip['contract'].get_ibc_previous(
                    data_payslip['period'].end, smmlv, True)
                value += (ibc_previous / 30) * no_pay_days
        total, rate = self._get_total_and_rate_for_ded_pens(
            data_payslip, value)

        if data_payslip['politics']['hr_payroll_co.does_not_allow_ibd_less_than_smmlv']:
            total, value = self._compute_base_less_tham_smmlv(
                data_payslip, rate)

        total -= data_payslip.get(TPCP, {}).get('DED_PENS', 0)
        data_payslip['DED_PENS'] = total

        return self._build_payslip_line_for_ded_pens(data_payslip, value, total, rate)

    def _DED_PENS_PUBLIC(self, data_payslip):
        if not self._apply_pension_reform(data_payslip):
            return

        is_teaching_phase = data_payslip['contract'].fiscal_type_id.code == '12'
        if not self._is_valid_for_ded_pens(data_payslip) or is_teaching_phase:
            return

        if data_payslip["contract"].is_transitional_regime:
            return

        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)

        ibd = data_payslip['IBD']

        # Cantidad maxima de SMMLV
        accai_threshold = data_payslip['economic_variables']['ACCAI_THRESHOLD'][data_payslip['current_year_month']]
        if not accai_threshold:
            raise ValidationError(
                'No se encontró el valor de <Límite de ingreso para aportar a ACCAI> para el año {}'.format(data_payslip['current_year_month']))
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]

        # Monto maximo de deduccion
        accai_threshold_amount = accai_threshold * smmlv

        deduction_amount = ibd if ibd < accai_threshold_amount else accai_threshold_amount

        total, _ = self._get_total_and_rate_for_ded_pens(
            data_payslip, deduction_amount)

        total -= data_payslip.get(TPCP, {}).get('DED_PENS_PUBLIC', 0)
        data_payslip['DED_PENS_PUBLIC'] = total

        rate = total / ibd * 100

        return self._build_payslip_line_for_ded_pens(data_payslip, deduction_amount, total, rate)

    def _DED_PENS_ACCAI(self, data_payslip):
        if not self._apply_pension_reform(data_payslip):
            return

        is_teaching_phase = data_payslip['contract'].fiscal_type_id.code == '12'
        if not self._is_valid_for_ded_pens(data_payslip) or is_teaching_phase:
            return

        if data_payslip["contract"].is_transitional_regime:
            return

        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)

        ibd = data_payslip['IBD']

        # Cantidad maxima de SMMLV
        accai_threshold = data_payslip['economic_variables']['ACCAI_THRESHOLD'][data_payslip['current_year_month']]
        if not accai_threshold:
            raise ValidationError(
                'No se encontró el valor de <Límite de ingreso para aportar a ACCAI> para el año {}'.format(data_payslip['current_year_month']))
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]

        # Monto maximo de deduccion
        accai_threshold_amount = accai_threshold * smmlv

        accai_deduction = ibd - accai_threshold_amount
        if accai_deduction <= 0:
            return

        total, _ = self._get_total_and_rate_for_ded_pens(
            data_payslip, accai_deduction)

        total -= data_payslip.get(TPCP, {}).get('DED_PENS_ACCAI', 0)
        data_payslip['DED_PENS_ACCAI'] = total

        rate = total / ibd * 100

        return self._build_payslip_line_for_ded_pens(data_payslip, accai_deduction, total, rate)
