# -*- coding: utf-8 -*-
from odoo import models, fields, api


class IncomeAndWithholdingCertificate(models.Model):
    _name = 'income.and.withholding.certificate'
    _description = 'Income and withholding certificate'

    template_id = fields.Many2one(
        'income.and.withholding.certificate.template', string='Plantilla')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', 'Empleado')

    year = fields.Char('Año gravable')
    form_number = fields.Char('Número de formulario', help="Campo 4")
    nit = fields.Integer('NIT', help="Campo 5")
    verification_code = fields.Integer('DV', help="Campo 6")
    retainer_first_last_name = fields.Char(
        'Primer apellido', help="Campo 7")
    retainer_second_last_name = fields.Char(
        'Segundo apellido', help="Campo 8")
    retainer_first_name = fields.Char(
        'Primer nombre', help="Campo 9")
    retainer_second_name = fields.Char(
        'Otros nombres', help="Campo 10")
    social_reason = fields.Char('Razón social', help="Campo 11")
    employee_document_type = fields.Char(
        'Tipo de documento', help="Campo 24; 12:TI,13:CC,21:TE,22:CE,31:NIT,41:PA")
    employee_vat = fields.Char(
        'Número de identificación', help="Campo 25")
    employee_first_last_name = fields.Char(
        'Primer apellido', help="Campo 26")
    employee_second_last_name = fields.Char(
        'Segundo apellido', help="Campo 27")
    employee_first_name = fields.Char(
        'Primer nombre', help="Campo 28")
    employee_second_name = fields.Char(
        'Otros nombres', help="Campo 29")
    date_from_year = fields.Char('Año desde', help="Campo 30")
    date_from_month = fields.Char('Mes desde', help="Campo 30")
    date_from_day = fields.Char('Día desde', help="Campo 30")
    date_to_year = fields.Char('Año hasta', help="Campo 31")
    date_to_month = fields.Char('Mes hasta', help="Campo 31")
    date_to_day = fields.Char('Día hasta', help="Campo 31")
    date_year = fields.Char('Año expedición', help="Campo 32")
    date_month = fields.Char('Mes expedición', help="Campo 32")
    date_day = fields.Char('Día expedición', help="Campo 32")
    holding_place = fields.Char(
        'Lugar donde se practicó la retención', help="Campo 33")
    departament_code = fields.Char(
        'Código del departamento', help="Campo 34")
    city_code = fields.Char(
        'Código de la ciudad/municipio', help="Campo 35")
    salary_payments = fields.Float('Pagos por salarios', help="Campo 36")
    bonus_payments = fields.Float(
        'Pagos realizados con bonos electrónicos, etc.', help="Campo 37")
    food_payments = fields.Float(
        'Pagos por alimentación mayores a 41 UVT', help="Campo 38")
    fee_payments = fields.Float(
        'Pagos por honorarios', help="Campo 39")
    service_payments = fields.Float(
        'Pagos por servicios', help="Campo 40")
    commission_payments = fields.Float(
        'Pagos por comisiones', help="Campo 41")
    social_benefit_payments = fields.Float(
        'Pagos por prestaciones sociales', help="Campo 42")
    travel_payments = fields.Float(
        'Pagos por viáticos', help="Campo 43")
    proxy_payments = fields.Float(
        'Pagos por gastos de representación', help="Campo 44")
    cooperative_work_payments = fields.Float(
        'Pagos por trabajo asociado cooperativo', help="Campo 45")
    other_payments = fields.Float(
        'Otros pagos', help="Campo 46")
    severance_payments = fields.Float(
        'Auxilio de cesantía e intereses pagados al empleado', help="Campo 47")
    severance_cst_payments = fields.Float(
        'Auxilio de cesantía del regimen tradicional CST', help="Campo 48")
    severance_fund_payments = fields.Float(
        'Auxilio de cesantía consignado al fondo', help="Campo 49")
    pension_payments = fields.Float(
        'Pensiones de jubilación, vejez o invalidez', help="Campo 50")
    financial_support_payments = fields.Float(
        'Apoyos económicos', help="Campo 51")
    total_payments = fields.Float(
        'Total de ingresos brutos', help="Campo 52")

    health_contributions = fields.Float(
        'Aportes a salud', help="Campo 53")
    pension_contributions = fields.Float(
        'Aportes a pensión', help="Campo 54")
    voluntary_contributions_rais = fields.Float(
        'Cotizaciones voluntarias RAIS', help="Campo 55")
    afp_contribution = fields.Float('Aportes a AFP', help="Campo 56")
    afc_contributions = fields.Float('Aportes a AFC', help="Campo 57")
    avc_contributions = fields.Float('Aportes a AVC', help="Campo 58")
    average_salary = fields.Float('Promedio salarial', help="Campo 59")

    withholding_tax = fields.Float(
        'Retención en la fuente por ingresos laborales y pensionales', help="Campo 60")
    retainer = fields.Char(
        'Nombre del pagador o agente retenedor', help="Campo 60.1")

    @api.depends('form_number')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f'Certificado-{record.form_number}'

    def send_mail(self):
        mail_template = self.env.ref(
            "hr_payroll_co.income_and_withholding_certificate_mail_template")
        mail_template.send_mail(self.id, force_send=True)
