# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    apply_contract_type_policy = fields.Boolean(
        string='Activar Política de Cálculo por Tipo de Contrato',
        config_parameter='hr_payroll_colombo.apply_contract_type_policy',
        default=False,
        help='Al activarla, el sistema exige la categoría de empleado, el '
             'subtipo de profesor y el valor hora en el contrato antes de '
             'liquidar, y aplica las bases de cálculo por tipo de contrato.')

    benefits_330_type_10 = fields.Boolean(
        string='Tipo 10: prestaciones sobre 330 días',
        config_parameter='hr_payroll_colombo.benefits_330_type_10')
    benefits_330_type_12 = fields.Boolean(
        string='Tipo 12: prestaciones sobre 330 días',
        config_parameter='hr_payroll_colombo.benefits_330_type_12')
    benefits_330_mixed = fields.Boolean(
        string='Mixto: prestaciones sobre 330 días',
        config_parameter='hr_payroll_colombo.benefits_330_mixed',
        help='En el contrato mixto aplica a todo el contrato: salario básico '
             'y horas.')

    teacher_provisions = fields.Boolean(
        string='Provisiones profesores',
        config_parameter='hr_payroll_colombo.teacher_provisions',
        default=False,
        help='Permite configurar porcentajes de provisión propios para los '
             'contratos de profesor, distintos de los administrativos. Se '
             'aplican tal cual sobre el valor de las horas del mes en los '
             'subtipos marcados; los demás provisionan como administrativos.')
    teacher_provisions_type_10 = fields.Boolean(
        string='Aplica a Tipo 10',
        config_parameter='hr_payroll_colombo.teacher_provisions_type_10')
    teacher_provisions_type_12 = fields.Boolean(
        string='Aplica a Tipo 12',
        config_parameter='hr_payroll_colombo.teacher_provisions_type_12')
    teacher_provisions_mixed = fields.Boolean(
        string='Aplica a Mixto',
        config_parameter='hr_payroll_colombo.teacher_provisions_mixed',
        help='En el contrato mixto solo la fracción de horas usa estos '
             'porcentajes; el salario básico provisiona como administrativo.')
    teacher_severance_percentage = fields.Float(
        string='Provisión cesantías %',
        config_parameter='hr_payroll_colombo.teacher_severance_percentage')
    teacher_interest_severance_percentage = fields.Float(
        string='Provisión int cesantías %',
        help='Porcentaje sobre la provisión de cesantías del profesor, igual '
             'que en las provisiones simples (por ley, 12 %).',
        config_parameter='hr_payroll_colombo.'
                         'teacher_interest_severance_percentage')
    teacher_prima_percentage = fields.Float(
        string='Provisión prima %',
        config_parameter='hr_payroll_colombo.teacher_prima_percentage')
    teacher_holidays_percentage = fields.Float(
        string='Provisión vacaciones %',
        config_parameter='hr_payroll_colombo.teacher_holidays_percentage')
