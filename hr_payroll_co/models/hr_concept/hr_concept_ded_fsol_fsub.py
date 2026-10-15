# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.hr_payroll_co.models.hr_concept.hr_concept_base import TPCP


class HrConcept(models.Model):
    _inherit = 'hr.concept'

    def _get_rate_from_table(self, data_payslip, table_code, base_value):
        table = data_payslip['economic_variables'][table_code][data_payslip['current_year_month']]
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]

        base = base_value / smmlv

        matching_rule = next((
            rule for rule in table
            if (rule.get('lower_limit') is not None or rule.get('upper_limit') is not None) and
               (rule.get('lower_limit') is None or base >= rule.get('lower_limit')) and
               (rule.get('upper_limit') is None or base < rule.get('upper_limit'))
        ), None)

        return matching_rule.get('rate', 0) if matching_rule else 0

    def _FOND_SOL(self, data_payslip):
        if data_payslip['contract'].contract_type_id.type_class == 'apr':
            return

        if not data_payslip['contract'].fiscal_subtype_id.code in ['00', False]:
            return

        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)

        rate = self._get_rate_from_table(
            data_payslip, 'FSOL', data_payslip['IBD'])

        if not rate:
            return

        previous = data_payslip.get(TPCP, {}).get('FOND_SOL', 0)
        total = data_payslip['IBD'] * rate / 100 - previous
        data_payslip['FOND_SOL'] = total

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

    def _FOND_SUB(self, data_payslip):
        if data_payslip['contract'].contract_type_id.type_class == 'apr':
            return

        if not data_payslip['contract'].fiscal_subtype_id.code in ['00', False]:
            return

        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)

        rate = self._get_rate_from_table(
            data_payslip, 'FSUB', data_payslip['IBD'])

        if not rate:
            return

        previous = data_payslip.get(TPCP, {}).get('FOND_SUB', 0)
        total = data_payslip['IBD'] * rate / 100 - previous
        data_payslip['FOND_SUB'] = total

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
