# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.fields import Domain


class IncomeAndWithholdingCertificateTemplate(models.Model):
    _name = 'income.and.withholding.certificate.template'
    _description = 'Income and withholding certificate template'

    template_date = fields.Date('Fecha de plantilla')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company, readonly=True)

    year_top = fields.Integer('Año gravable (superior)')
    year_left = fields.Integer('Año gravable (izquierda)')
    form_number_top = fields.Integer('Número de formulario (superior)')
    form_number_left = fields.Integer('Número de formulario (izquierda)')
    nit_top = fields.Integer('NIT (superior)')
    nit_left = fields.Integer('NIT (izquierda)')
    verification_code_top = fields.Integer('Dígito de verificación (superior)')
    verification_code_left = fields.Integer(
        'Dígito de verificación (izquierda)')
    retainer_first_last_name_top = fields.Integer(
        'Primer apellido (superior)')
    retainer_first_last_name_left = fields.Integer(
        'Primer apellido (izquierda)')
    retainer_second_last_name_top = fields.Integer(
        'Segundo apellido (superior)')
    retainer_second_last_name_left = fields.Integer(
        'Segundo apellido (izquierda)')
    retainer_first_name_top = fields.Integer(
        'Primer nombre (superior)')
    retainer_first_name_left = fields.Integer(
        'Primer nombre (izquierda)')
    retainer_second_name_top = fields.Integer(
        'Otros nombres (superior)')
    retainer_second_name_left = fields.Integer(
        'Otros nombres (izquierda)')
    social_reason_top = fields.Integer('Razón social (superior)')
    social_reason_left = fields.Integer('Razón social (izquierda)')
    employee_document_type_top = fields.Integer(
        'Tipo de documento (superior)')
    employee_document_type_left = fields.Integer(
        'Tipo de documento (izquierda)')
    employee_vat_top = fields.Integer('Número de identificación (superior)')
    employee_vat_left = fields.Integer('Número de identificación (izquierda)')

    employee_first_last_name_top = fields.Integer(
        'Primer apellido (superior)')
    employee_first_last_name_left = fields.Integer(
        'Primer apellido (izquierda)')
    employee_second_last_name_top = fields.Integer(
        'Segundo apellido (superior)')
    employee_second_last_name_left = fields.Integer(
        'Segundo apellido (izquierda)')
    employee_first_name_top = fields.Integer('Primer nombre (superior)')
    employee_first_name_left = fields.Integer('Primer nombre (izquierda)')
    employee_second_name_top = fields.Integer('Otros nombres (superior)')
    employee_second_name_left = fields.Integer('Otros nombres (izquierda)')


    date_from_year_top = fields.Integer('Año desde (superior)')
    date_from_year_left = fields.Integer('Año desde (izquierda)')
    date_from_month_top = fields.Integer('Mes desde (superior)')
    date_from_month_left = fields.Integer('Mes desde (izquierda)')
    date_from_day_top = fields.Integer('Día desde (superior)')
    date_from_day_left = fields.Integer('Día desde (izquierda)')
    date_to_year_top = fields.Integer('Año hasta (superior)')
    date_to_year_left = fields.Integer('Año hasta (izquierda)')
    date_to_month_top = fields.Integer('Mes hasta (superior)')
    date_to_month_left = fields.Integer('Mes hasta (izquierda)')
    date_to_day_top = fields.Integer('Día hasta (superior)')
    date_to_day_left = fields.Integer('Día hasta (izquierda)')
    date_year_top = fields.Integer('Año expedición (superior)')
    date_year_left = fields.Integer('Año expedición (izquierda)')
    date_month_top = fields.Integer('Mes expedición (superior)')
    date_month_left = fields.Integer('Mes expedición (izquierda)')
    date_day_top = fields.Integer('Día expedición (superior)')
    date_day_left = fields.Integer('Día expedición (izquierda)')
    holding_place_top = fields.Integer(
        'Lugar donde se practico la retención (superior)')
    holding_place_left = fields.Integer(
        'Lugar donde se practico la retención (izquierda)')
    departament_code_top = fields.Integer(
        'Código del departamento (superior)')
    departament_code_left = fields.Integer(
        'Código del departamento (izquierda)')
    city_code_top = fields.Integer(
        'Código de la ciudad/municipio (superior)')
    city_code_left = fields.Integer(
        'Código de la ciudad/municipio (izquierda)')
    salary_payments_top = fields.Integer('Pagos por salarios (superior)')
    salary_payments_left = fields.Integer('Pagos por salarios (izquierda)')
    bonus_payments_top = fields.Integer(
        'Pagos realizados con bonos electrónicos, etc. (superior)')
    bonus_payments_left = fields.Integer(
        'Pagos realizados con bonos electrónicos, etc. (izquierda)')
    food_payments_top = fields.Integer(
        'Pagos por alimentación mayores a 41 UVT (superior)')
    food_payments_left = fields.Integer(
        'Pagos por alimentación mayores a 41 UVT (izquierda)')
    fee_payments_top = fields.Integer('Pagos por honorarios (superior)')
    fee_payments_left = fields.Integer('Pagos por honorarios (izquierda)')
    service_payments_top = fields.Integer('Pagos por servicios (superior)')
    service_payments_left = fields.Integer('Pagos por servicios (izquierda)')
    commission_payments_top = fields.Integer(
        'Pagos por comisiones (superior)')
    commission_payments_left = fields.Integer(
        'Pagos por comisiones (izquierda)')
    social_benefit_payments_top = fields.Integer(
        'Pagos por prestaciones sociales (superior)')
    social_benefit_payments_left = fields.Integer(
        'Pagos por prestaciones sociales (izquierda)')
    travel_payments_top = fields.Integer('Pagos por viáticos (superior)')
    travel_payments_left = fields.Integer('Pagos por viáticos (izquierda)')
    proxy_payments_top = fields.Integer(
        'Pagos por gastos de representación (superior)')
    proxy_payments_left = fields.Integer(
        'Pagos por gastos de representación (izquierda)')
    cooperative_work_payments_top = fields.Integer(
        'Pagos por trabajo asociado cooperativo (superior)')
    cooperative_work_payments_left = fields.Integer(
        'Pagos por trabajo asociado cooperativo (izquierda)')
    other_payments_top = fields.Integer('Otros pagos (superior)')
    other_payments_left = fields.Integer('Otros pagos (izquierda)')
    severance_payments_top = fields.Integer(
        'Auxilio de cesantía e intereses pagados al empleado (superior)')
    severance_payments_left = fields.Integer(
        'Auxilio de cesantía e intereses pagados al empleado (izquierda)')
    severance_cst_payments_top = fields.Integer(
        'Auxilio de cesantía del regimen tradicional CST (superior)')
    severance_cst_payments_left = fields.Integer(
        'Auxilio de cesantía del regimen tradicional CST (izquierda)')
    severance_fund_payments_top = fields.Integer(
        'Auxilio de cesantía consignado al fondo (superior)')
    severance_fund_payments_left = fields.Integer(
        'Auxilio de cesantía consignado al fondo (izquierda)')
    pension_payments_top = fields.Integer(
        'Pensiones de jubilación, vejez o invalidez (superior)')
    pension_payments_left = fields.Integer(
        'Pensiones de jubilación, vejez o invalidez (izquierda)')
    financial_support_payments_top = fields.Integer(
        'Apoyos económicos (superior)')
    financial_support_payments_left = fields.Integer(
        'Apoyos económicos (izquierda)')
    total_payments_top = fields.Integer('Total de ingresos brutos (superior)')
    total_payments_left = fields.Integer(
        'Total de ingresos brutos (izquierda)')
    health_contributions_top = fields.Integer('Aportes a salud (superior)')
    health_contributions_left = fields.Integer('Aportes a salud (izquierda)')
    pension_contributions_top = fields.Integer('Aportes a pensión (superior)')
    pension_contributions_left = fields.Integer(
        'Aportes a pensión (izquierda)')
    voluntary_contributions_rais_top = fields.Integer(
        'Cotizaciones voluntarias RAIS (superior)')
    voluntary_contributions_rais_left = fields.Integer(
        'Cotizaciones voluntarias RAIS (izquierda)')
    afp_contribution_top = fields.Integer('Aportes a AFP (superior)')
    afp_contribution_left = fields.Integer('Aportes a AFP (izquierda)')
    afc_contributions_top = fields.Integer('Aportes a AFC (superior)')
    afc_contributions_left = fields.Integer('Aportes a AFC (izquierda)')
    avc_contributions_top = fields.Integer('Aportes a AVC (superior)')
    avc_contributions_left = fields.Integer('Aportes a AVC (izquierda)')
    average_salary_top = fields.Integer('Promedio salarial (superior)')
    average_salary_left = fields.Integer('Promedio salarial (izquierda)')
    withholding_tax_top = fields.Integer(
        'Retención en la fuente por ingresos laborales y pensionales (superior)')
    withholding_tax_left = fields.Integer(
        'Retención en la fuente por ingresos laborales y pensionales (izquierda)')
    retainer_top = fields.Integer(
        'Nombre del pagador o agente retenedor (superior)')
    retainer_left = fields.Integer(
        'Nombre del pagador o agente retenedor (izquierda)')

    # Compute concepts
    salary_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_salary_rel', domain="[('company_id', '=', company_id)]", string='Pagos por salarios', help="Campo 36")
    bonus_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_bonus_rel', domain="[('company_id', '=', company_id)]", string='Pagos realizados con bonos electrónicos, etc.', help="Campo 37")
    food_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_food_rel', domain="[('company_id', '=', company_id)]", string='Pagos por alimentación mayores a 41 UVT', help="Campo 38")
    fee_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_fee_rel', domain="[('company_id', '=', company_id)]", string='Pagos por honorarios', help="Campo 39")
    service_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_service_rel', domain="[('company_id', '=', company_id)]", string='Pagos por servicios', help="Campo 40")
    commission_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_commision_rel', domain="[('company_id', '=', company_id)]", string='Pagos por comisiones', help="Campo 41")
    social_benefit_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_social_benefit_rel', domain="[('company_id', '=', company_id)]", string='Pagos por prestaciones sociales', help="Campo 42")
    travel_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_travel_rel', domain="[('company_id', '=', company_id)]", string='Pagos por viáticos', help="Campo 43")
    proxy_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_proxy_rel', domain="[('company_id', '=', company_id)]", string='Pagos por gastos de representación', help="Campo 44")
    cooperative_work_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_cooperative_work_rel', domain="[('company_id', '=', company_id)]", string='Pagos por trabajo asociado cooperativo', help="Campo 45")
    other_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_other_rel', domain="[('company_id', '=', company_id)]", string='Otros pagos', help="Campo 46")
    severance_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_severance_rel', domain="[('company_id', '=', company_id)]", string='Auxilio de cesantía e intereses pagados al empleado', help="Campo 47")
    severance_cst_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_severance_cst_rel', domain="[('company_id', '=', company_id)]", string='Auxilio de cesantía del regimen tradicional CST', help="Campo 48")
    severance_fund_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_severance_fund_rel', domain="[('company_id', '=', company_id)]", string='Auxilio de cesantía consignado al fondo', help="Campo 49")
    pension_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_pension_rel', domain="[('company_id', '=', company_id)]", string='Pensiones de jubilación, vejez o invalidez', help="Campo 50")
    financial_support_payments = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_financial_support_rel', domain="[('company_id', '=', company_id)]", string='Apoyos económicos', help="Campo 51")

    health_contributions = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_health_rel', domain="[('company_id', '=', company_id)]", string='Aportes a salud', help="Campo 53")
    pension_contributions = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_pension_contribution_rel', domain="[('company_id', '=', company_id)]", string='Aportes a pensión', help="Campo 54")
    voluntary_contributions_rais = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_rais_rel', domain="[('company_id', '=', company_id)]", string='Cotizaciones voluntarias RAIS', help="Campo 55")
    afp_contribution = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_afp_rel', domain="[('company_id', '=', company_id)]", string='Cotizaciones voluntarias', help="Campo 56")
    afc_contributions = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_afc_rel', domain="[('company_id', '=', company_id)]", string='Aportes a AFC', help="Campo 57")
    avc_contributions = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_avc_rel', domain="[('company_id', '=', company_id)]", string='Aportes a AVC', help="Campo 58")

    withholding_tax = fields.Many2many(
        comodel_name='income.and.withholding.concepts', relation='iwt_iwc_withholding_tax_rel', domain="[('company_id', '=', company_id)]", string='Retención en la fuente por ingresos laborales y pensionales', help="Campo 60")

    @api.depends('company_id', 'template_date')
    def _compute_display_name(self):
        if len(self) == 1:
            self.env['income.and.withholding.concepts'].load()
        for record in self:
            name = f'Plantilla-{record.company_id.name}'
            if record.template_date:
                name += f'-{record.template_date.year}'
            record.display_name = name
    
    @api.model
    def _name_search(self, name, domain=None, operator='ilike',
                     limit=None, order=None):
        domain = domain or []
        if operator != 'ilike' and not (name or '').strip():
            domain = Domain.AND([[('display_name', 'ilike', name)], domain])
        return self._search(domain, limit=limit, order=order)
