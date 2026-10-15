# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pays_sub_trans_train_prod = fields.Boolean(
        string="Paga subsidio de transporte a aprendices en etapa productiva",
        config_parameter='hr_payroll_co.pays_sub_trans_train_prod',
        default=False)
    eps_rate_employee = fields.Float(
        string='EPS para empleado',
        config_parameter='hr_payroll_co.eps_rate_employee')
    eps_rate_employer = fields.Float(
        string='EPS para empleador',
        config_parameter='hr_payroll_co.eps_rate_employer')
    pen_rate_employee = fields.Float(
        string='Pensión para empleado',
        config_parameter='hr_payroll_co.pen_rate_employee')
    pen_rate_employer = fields.Float(
        string='Pensión para empleador',
        config_parameter='hr_payroll_co.pen_rate_employer')
    pays_eg_b2_with_wage = fields.Boolean(
        string="Paga 1-2 dias de incapacidad de enfermedad general con salario",
        config_parameter='hr_payroll_co.pays_eg_b2_with_wage',
        default=False)
    pays_eg_general_complement = fields.Boolean(
        string="Paga complemento de incapacidad por enfermedad general",
        config_parameter='hr_payroll_co.pays_eg_general_complement',
        default=False,
        help="Si está activo, la empresa reconoce en nómina la diferencia entre el 100% del "
        "salario/IBC y el porcentaje reconocido por la EPS en cada tramo de incapacidad.")
    pays_atep_b1_with_wage = fields.Boolean(
        string="Paga 1 dia de accidente de trabajo - anfermedad profesional con salario",
        config_parameter='hr_payroll_co.pays_atep_b1_with_wage',
        default=False)
    discount_suspensions = fields.Boolean(
        string="Descuenta días de suspensión en prima",
        config_parameter='hr_payroll_co.discount_suspensions',
        default=False)
    average_sub_trans = fields.Boolean(
        string="Promediar subsidio de transporte en prestaciones sociales",
        config_parameter='hr_payroll_co.average_sub_trans',
        default=False)
    pay_ccf_mat_pat = fields.Boolean(
        string="Cotiza CCF en licencias de MAT o PAT",
        config_parameter='hr_payroll_co.pay_ccf_mat_pat',
        default=False)

    compute_simple_provisions = fields.Boolean(
        string='Calcular provisiones simples',
        config_parameter="hr_payroll_co.compute_simple_provisions")

    holidays_percentage = fields.Float(
        string='Porcentaje de vacaciones',
        config_parameter="hr_payroll_co.holidays_percentage")
    prima_percentage = fields.Float(
        string='Porcentaje de prima',
        config_parameter="hr_payroll_co.prima_percentage")
    severance_percentage = fields.Float(
        string='Porcentaje de cesantias',
        config_parameter="hr_payroll_co.severance_percentage")
    interest_severance_percentage = fields.Float(
        string='Porcentaje de intereses de cesantias',
        config_parameter="hr_payroll_co.interest_severance_percentage")
    social_benefits_with_last_wage = fields.Boolean(
        string='Calcular prestaciones sociales con el último salario',
        config_parameter="hr_payroll_co.social_benefits_with_last_wage")

    deductions_with_previous_ibc = fields.Boolean(
        string='Cálculo salud y pensión de vacaciones disfrutadas en nómina con IBC del mes anterior',
        config_parameter="hr_payroll_co.deductions_with_previous_ibc")
    does_not_allow_ibd_less_than_smmlv = fields.Boolean(
        string='No permite IBD menor al SMMLV',
        config_parameter="hr_payroll_co.does_not_allow_ibd_less_than_smmlv")
    average_prima_in_settlement_less_than_month = fields.Boolean(
        string='Promediar prima por trabajo menor a un mes',
        config_parameter="hr_payroll_co.average_prima_in_settlement_less_than_month")
    discount_all_leave_in_social_benefits = fields.Boolean(
        string='Descontar total de ausencias no pagadas en prestaciones sociales',
        config_parameter="hr_payroll_co.discount_all_leave_in_social_benefits")

    accumulated_minimum_top_40 = fields.Boolean(
        string='Acumulado minimo de Tope40',
        config_parameter="hr_payroll_co.accumulated_minimum_top_40")
    pay_sub_trans_in_q2 = fields.Boolean(
        string='Pagar subsidio de transporte en segunda quincena',
        config_parameter="hr_payroll_co.pay_sub_trans_in_q2")
    pay_advance_vacation = fields.Boolean(
        string='Pagar vacaciones de forma anticipada',
        config_parameter="hr_payroll_co.pay_advance_vacation"
    )
    pila_with_previous_ibc = fields.Boolean(
        string='Cálculo del IBC en PILA de vacaciones disfrutadas con IBC del mes anterior',
        config_parameter="hr_payroll_co.pila_with_previous_ibc",
        help="Si está activo, en la planilla PILA el IBC de la línea de ausencia por "
        "vacaciones toma SIEMPRE el IBC del mes inmediatamente anterior al inicio de las "
        "vacaciones, aun cuando el disfrute cruce a otro mes. Sin la política, el tramo que "
        "cae en un mes posterior toma el IBC del mes anterior a ese tramo."
    )

    apply_parafiscal_pila = fields.Boolean(
        string='Aporte parafiscales 10 salarios mínimos en PILA',
        config_parameter="hr_payroll_co.apply_parafiscal_pila"
    )
    discount_leave_days_in_retroactive = fields.Boolean(
        string='Descontar días de ausencias en retroactivos',
        config_parameter="hr_payroll_co.discount_leave_days_in_retroactive"
    )
    assumed_disability_february = fields.Boolean(
        string='Incapacidad asumida en febrero',
        config_parameter="hr_payroll_co.assumed_disability_february"
    )
    assumed_pen_not_remunerate_licences = fields.Boolean(
        string='Licencias no remuneradas asumida en pension',
        config_parameter="hr_payroll_co.assumed_pen_not_remunerate_licences"
    )
    full_quote_february_pila = fields.Boolean(
        string='Días cotización (30) en PILA cuando retiro es el último día de febrero',
        config_parameter="hr_payroll_co.full_quote_february_pila"
    )
    pay_ccf_leave_pay = fields.Boolean(
        string="Cotiza CCF en ausentismos con pago",
        config_parameter='hr_payroll_co.pay_ccf_leave_pay',
        default=False)
    apply_no_pay_leave_intces = fields.Boolean(
        string='Ignorar ausencias no pagadas en intereses de cesantias',
        config_parameter="hr_payroll_co.apply_no_pay_leave_intces")
    apply_no_pay_leave_ces = fields.Boolean(
        string='Ignorar ausencias no pagadas en cesantias',
        config_parameter="hr_payroll_co.apply_no_pay_leave_ces")

    apply_prim_conv = fields.Boolean(
        string="Aplica convención",
        config_parameter='hr_payroll_co.apply_prim_conv',
        default=False)
    days_in_prim_conv = fields.Float(
        string="Días a pagar en prima convención",
        config_parameter='hr_payroll_co.days_in_prim_conv',
        default=24.0)
    days_in_prim_vac_conv = fields.Float(
        string="Días a pagar en prima vacaciones convención",
        config_parameter='hr_payroll_co.days_in_prim_vac_conv',
        default=30.0)
    percentage_prv_prim_conv = fields.Float(
        string='% Provision prima convención',
        config_parameter="hr_payroll_co.percentage_prv_prim_conv",
        default=13.33)
    percentage_prv_prim_liq_conv = fields.Float(
        string='% Provision prima liquidacion convención',
        config_parameter="hr_payroll_co.percentage_prv_prim_liq_conv",
        default=8.33)
    percentage_ded_eps_conv = fields.Float(
        string='% Deduccion salud convención',
        config_parameter="hr_payroll_co.percentage_ded_eps_conv",
        default=0.33)

    total_avg_holidays = fields.Boolean(
        string='Promedio total en vacaciones',
        config_parameter="hr_payroll_co.total_avg_holidays",
    )

    include_social_base_report = fields.Boolean(
        related='company_id.include_social_base_report',
        readonly=False
    )

    public_pension_administrator = fields.Many2one(
        'res.partner',
        string='Administrador público de pensiones',
        config_parameter='hr_payroll_co.public_pension_administrator'
    )
    analytic_distribution_contract = fields.Boolean(
        related='company_id.analytic_distribution_contract',
        readonly=False
    )
    allow_analytic_distribution_over_100 = fields.Boolean(
        related='company_id.allow_analytic_distribution_over_100',
        readonly=False
    )

    dont_apply_labor_reform = fields.Boolean(
        string="No aplicar reforma laboral 2025",
        config_parameter='hr_payroll_co.dont_apply_labor_reform',
        default=False)
    prima_avg_variable = fields.Boolean(
        string='Promedio variable prima y cesantias',
        config_parameter='hr_payroll_co.prima_avg_variable',
        default=False)
    take_net_salary_in_pila = fields.Boolean(
        string='Tomar salario de contrato en PILA',
        config_parameter='hr_payroll_co.take_net_salary_in_pila',
        default=False)

    use_partner_like_coach = fields.Boolean(
        related='company_id.use_partner_like_coach',
        readonly=False
    )

    percentage_prv_nav = fields.Float(
        related='company_id.percentage_prv_nav',
        readonly=False,
        string='Porcentaje Provisión Prima Navidad'
    )
    percentage_prv_day_31 = fields.Float(
        related='company_id.percentage_prv_day_31',
        readonly=False,
        string='Porcentaje Provisión día 31'
    )
    percentage_prv_aux_vac = fields.Float(
        related='company_id.percentage_prv_aux_vac',
        readonly=False,
        string='Porcentaje Provisión Auxilio Vacaciones'
    )
    percentage_prv_old = fields.Float(
        related='company_id.percentage_prv_old',
        readonly=False,
        string='Porcentaje Provisión Antiguedad'
    )

    sub_trans_q1_with_incomes = fields.Boolean(
        string="Subsidio de transporte con ingresos adicionales en Q1",
        config_parameter='hr_payroll_co.sub_trans_q1_with_incomes',
        default=False
    )
    decimal_in_payroll_pdf = fields.Integer(
        related='company_id.decimal_in_payroll_pdf',
        readonly=False,
        string='Decimales en PDF de nómina'
    )
    intces_days_with_last_page = fields.Boolean(
        string='Días de intereses de cesantías a partir de último pago',
        config_parameter="hr_payroll_co.intces_days_with_last_page"
    )
    decimal_in_income_cert_pdf = fields.Integer(
        related='company_id.decimal_in_income_cert_pdf',
        readonly=False,
        string='Decimales en PDF de Certificado de ingresos y retenciones'
    )
    calculate_hr_holiday_book_period = fields.Boolean(
        related="company_id.calculate_hr_holiday_book_period",
        string='Calcular libro de vacaciones por periodo', 
        default=False,
        readonly=False
    )
    day31_wage_novelty_type_id = fields.Many2one(
        related='company_id.day31_wage_novelty_type_id',
        readonly=False)
    day31_transport_novelty_type_id = fields.Many2one(
        related='company_id.day31_transport_novelty_type_id',
        readonly=False)
    show_loan_balance_in_payslip = fields.Boolean(
        related='company_id.show_loan_balance_in_payslip',
        readonly=False,
    )
    show_settlement_type_in_report = fields.Boolean(
        related='company_id.show_settlement_type_in_report',
        readonly=False,
    )
    include_comp_earnings_in_prv_vac = fields.Boolean(
        string='Incluir ingresos complementarios en provisión de vacaciones',
        config_parameter="hr_payroll_co.include_comp_earnings_in_prv_vac"
    )
