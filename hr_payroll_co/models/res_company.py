# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    arl_id = fields.Many2one(
        comodel_name='res.partner', string='ARL', domain="[('arl','=','True')]")
    work_certificate_sign = fields.Binary(
        string="Firma Certificado Laboral")
    work_certificate_sign_text = fields.Html(
        string="Texto en Firma de Cetificado Laboral")
    use_liquidation_custom_footer = fields.Boolean(
        string='Usar texto y firma en liquidacion')
    liquidation_payslip_text = fields.Html(
        string='Texto desprendible de liquidacion')
    liquidation_payslip_sign = fields.Binary(
        string='Firma desprendible de liquidacion')
    liquidation_payslip_sign_text = fields.Html(
        string='Texto firma desprendible de liquidacion')
    show_prepared_by = fields.Boolean(
        string="Mostrar 'Elaborado por'",
        help="Muestra el campo 'Elaborado por' en el desprendible de liquidación de contrato.")
    prepared_by_name = fields.Char(
        string='Nombre elaborado por',
        help="Nombre que aparece en 'Elaborado por'. Si se deja vacío se imprime una línea para diligenciar a mano.")

    include_social_base_report = fields.Boolean(
        string='Incluir base de prestaciones en formato de nómina',
    )
    analytic_distribution_contract = fields.Boolean(
        string='Distribución analítica nativa en contratos'
    )
    use_partner_like_coach = fields.Boolean(
        string='Usar el modelo de contactos como mentor',
        help='Si está activo, los mentores serán contactos (res.partner) en lugar de usuarios (res.users).'
    )
    allow_analytic_distribution_over_100 = fields.Boolean(
        string='Permitir distribución analítica mayor a 100%'
    )
    percentage_prv_nav = fields.Float(
        string='Porcentaje Provisión Prima Navidad'
    )
    percentage_prv_day_31 = fields.Float(
        string='Porcentaje Provisión día 31'
    )
    percentage_prv_aux_vac = fields.Float(
        string='Porcentaje Provisión Auxilio Vacaciones'
    )
    percentage_prv_old = fields.Float(
        string='Porcentaje Provisión Antiguedad'
    )
    decimal_in_payroll_pdf = fields.Integer(
        string='Decimales en PDF de nómina', default=0
    )
    decimal_in_income_cert_pdf = fields.Integer(
        string='Decimales en PDF de Certificado de ingresos y retenciones', default=1
    )
    calculate_hr_holiday_book_period = fields.Boolean(
        string='Calcular libro de vacaciones por periodo', default=False
    )
    use_custom_settlement_constancy = fields.Boolean(
        string='Usar constancia personalizada en liquidación', default=False
    )
    settlement_constancy_text = fields.Html(
        string='Texto de constancia de liquidación',
        sanitize_overridable=True,
    )
    show_loan_balance_in_payslip = fields.Boolean(
        string='Mostrar saldo pendiente de prestamos en desprendible',
        default=False,
    )
    show_settlement_type_in_report = fields.Boolean(
        string='Mostrar tipo de finalización en desprendible de liquidación',
        default=False,
    )
    day31_wage_novelty_type_id = fields.Many2one(
        comodel_name='hr.novelty.type', string='Categoría día 31 de salario',
        check_company=True)
    day31_transport_novelty_type_id = fields.Many2one(
        comodel_name='hr.novelty.type',
        string='Categoría día 31 de subsidio de transporte',
        check_company=True)
