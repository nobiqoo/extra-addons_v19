# -*- coding: utf-8 -*-
from odoo import models

POLITICS = {
    'hr_payroll_colombo.apply_contract_type_policy': bool,
    'hr_payroll_colombo.teacher_provisions': bool,
    'hr_payroll_colombo.teacher_severance_percentage': float,
    'hr_payroll_colombo.teacher_interest_severance_percentage': float,
    'hr_payroll_colombo.teacher_prima_percentage': float,
    'hr_payroll_colombo.teacher_holidays_percentage': float,
    'hr_payroll_colombo.teacher_provisions_type_10': bool,
    'hr_payroll_colombo.teacher_provisions_type_12': bool,
    'hr_payroll_colombo.teacher_provisions_mixed': bool,
}


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_politics(self):
        politics = super()._get_politics()
        config = self.env['ir.config_parameter'].sudo()
        for param, cast in POLITICS.items():
            politics[param] = cast(config.get_param(param))
        return politics

    def evaluate_constraints(self):
        res = super().evaluate_constraints()
        self.contract_id.check_contract_type_policy()
        return res

    def _get_distribution(self, account, payslip_line=None):
        """En los contratos de profesor la distribución analítica sale de la
        matriz de porcentajes por curso de las horas del mes, no de la
        distribución fija del contrato.

        En el contrato mixto conviven las dos: las líneas de la fracción
        administrativa conservan la cuenta analítica por defecto del contrato
        y solo las de la fracción de profesor heredan la matriz por curso.
        """
        if not self.contract_id.has_teacher_fraction():
            return super()._get_distribution(account, payslip_line)
        if not (account.code and account.code[0] in ('4', '5', '6', '7')):
            return super()._get_distribution(account, payslip_line)
        if payslip_line is not None and not self._is_teacher_line(payslip_line):
            if self.contract_id.has_administrative_fraction():
                return super()._get_distribution(account, payslip_line)
        distribution = self.get_teacher_hours_novelties()\
            .get_teacher_analytic_distribution()
        return distribution or super()._get_distribution(account, payslip_line)

    def update_data_payslip(self, data_payslip, payslip_line):
        """Lleva aparte, por categoría, el valor de las horas del profesor que
        entra a la nómina en curso, para poder excluirlo de la base de la
        provisión administrativa del contrato mixto."""
        res = super().update_data_payslip(data_payslip, payslip_line)
        novelty_id = payslip_line.get('novelty_id')
        if novelty_id and self.env['hr.novelty'].browse(
                novelty_id).is_teacher_hours:
            current_hours = data_payslip.setdefault('TEACHER_HOURS_CURRENT', {})
            category = payslip_line['category']
            current_hours[category] = (current_hours.get(category, 0)
                                       + payslip_line['total'])
        return res

    def _build_basic_wage(self):
        """Las horas del profesor se reportan a la DIAN como sueldo trabajado.

        La novedad de horas está homologada con el concepto DIAN Básico, así
        que su valor ya se suma al sueldo trabajado. Su cantidad, en cambio,
        son horas y no días: los días trabajados se toman solo de la línea de
        salario básico, que en el profesor Tipo 10 o Tipo 12 queda en cero
        pero conserva los días.
        """
        res = super()._build_basic_wage()
        teacher_lines = self.payslip_line_ids.filtered(
            lambda line: line.novelty_id.is_teacher_hours)
        if not teacher_lines:
            return res
        basic_lines = self.payslip_line_ids.filtered(
            lambda line: line.concept_id.code == 'BASICO')
        res['Dev_Bas_DiasTrabajados'] = sum(basic_lines.mapped('qty'))
        return res

    def _is_teacher_line(self, payslip_line):
        """La línea corresponde a la fracción de profesor: el devengo de las
        horas o una provisión liquidada sobre ellas."""
        if payslip_line.novelty_id and payslip_line.novelty_id.is_teacher_hours:
            return True
        return (payslip_line.concept_id.code or '').endswith('_PROF')

    def get_teacher_hours_novelties(self):
        """Novedades de horas de profesor que afectan el periodo liquidado."""
        self.ensure_one()
        return self.env['hr.novelty'].search([
            ('contract_id', '=', self.contract_id.id),
            ('is_teacher_hours', '=', True),
            ('state', 'in', ('validated', 'paid')),
            ('date_start', '>=', self.period_id.start.replace(day=1)),
            ('date_start', '<=', self.period_id.end),
        ])
