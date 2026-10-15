# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContributionFormLine(models.Model):
    _name = 'hr.contribution.form.line'
    _description = 'Detalle de planilla de aportes'

    contribution_id = fields.Many2one(
        comodel_name='hr.contribution.form', string='Planilla de aportes', required=True)
    contract_id = fields.Many2one(
        comodel_name='hr.contract', string='Contrato', required=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', related='contract_id.employee_id')
    leave_id = fields.Many2one(comodel_name='hr.leave', string='Ausencia')
    main = fields.Boolean(default=False, string='')

    # INDICADORES
    ing = fields.Selection(
        string='Ingreso', selection=[('X', 'X'), ('R', 'R'), ('C', 'C'), (' ', ' ')])
    ret = fields.Selection(
        string='Retiro', selection=[('X', 'X'), ('R', 'R'), ('C', 'C'), ('P', 'P'), (' ', ' ')])
    tde = fields.Boolean(default=False, string='Traslado desde EPS')
    tae = fields.Boolean(default=False, string='Traslado a EPS')
    tdp = fields.Boolean(
        default=False, string='Traslado desde fondo de pensiones')
    tap = fields.Boolean(default=False, string='Traslado a fondo de pensiones')
    vsp = fields.Boolean(
        default=False, string='Variación permanente de salario')
    fixes = fields.Selection(
        string='Correcciones', selection=[('A', 'A'), ('C', 'C'), (' ', ' ')])
    vst = fields.Boolean(
        default=False, string='Variación transitoria de salario')
    sln = fields.Boolean(default=False, string='Licencia no remunerada')
    ige = fields.Boolean(default=False, string='Incapacidad general')
    lma = fields.Boolean(
        default=False, string='Licencia de maternidad/paternidad')
    vac_lr = fields.Selection(
        string='Vacaciones-Licencia Remunerada', selection=[('X', 'X'), ('L', 'L'), (' ', ' ')])
    avp = fields.Boolean(default=False, string='Aporte voluntario')
    vct = fields.Boolean(
        default=False, string='Variación de centros de trabajo')
    irl = fields.Integer(string='Días de AT/EP')

    afp_code = fields.Char(string='Código AFP')
    afp_to_code = fields.Char(string='Código AFP traslado')
    eps_code = fields.Char(string='Código EPS')
    eps_to_code = fields.Char(string='Código EPS traslado')
    ccf_code = fields.Char(string='Código CCF')

    # COTIZACION
    pens_days = fields.Integer(string='Días cotizados pensión')
    eps_days = fields.Integer(string='Días cotizados EPS')
    arl_days = fields.Integer(string='Días cotizados ARL')
    ccf_days = fields.Integer(string='Días cotizados CCF')
    w_hours = fields.Integer(string='Horas laboradas')
    global_ibc = fields.Float(string='IBC Global')
    wage = fields.Float(string='Salario básico')
    wage_type = fields.Selection(
        string='Tipo de salario', selection=[('X', 'Integral'), ('F', 'Fijo'), ('V', 'Variable'), (' ', 'Aprendiz')])
    pens_ibc = fields.Float(string='IBC pensión')
    eps_ibc = fields.Float(string='IBC EPS')
    arl_ibc = fields.Float(string='IBC ARL')
    ccf_ibc = fields.Float(string='IBC CCF')
    other_ibc = fields.Float(string='IBC otros parafiscales')

    # Aportes AFP EPS
    pens_rate = fields.Float(string='Tarifa pensión')
    pens_cot = fields.Float(string='Cotización pensión')
    ap_vol_contributor = fields.Float(
        string='Aportes voluntarios del afiliado')
    ap_vol_company = fields.Float(string='Aportes voluntarios del aportante')
    pens_total = fields.Float(string='Aportes totales de pensión')
    fsol = fields.Float(string='Aportes a fondo de solidaridad')
    fsub = fields.Float(string='Aportes a fondo de subsistencia')
    ret_cont_vol = fields.Float(
        string='Valor no retenido por aportes voluntarios')

    # Reformal pensional
    pens_public = fields.Float(string='Aportes al fondo público')
    pens_accai = fields.Float(string='Aportes a ACCAI')

    eps_rate = fields.Float(string='Tarifa EPS')
    eps_cot = fields.Float(string='Cotización EPS')
    ups = fields.Float(string='Total UPS')
    aus_auth = fields.Char(string='Número de autorización')
    gd_amount = fields.Float(string='Valor de la incapacidad')
    # mat_auth = fields.Char(string='Número de autorización')
    mat_auth = fields.Char(string='Núm de autorización')
    mat_amount = fields.Float(string='Valor de la licencia')

    # ARL Y PARAFISCALES
    work_center = fields.Char(string='Centro de trabajo')
    fiscal_code = fields.Char(string='Código fiscal')
    arl_rate = fields.Float(string='Tarifa ARL')
    arl_cot = fields.Float(string='Cotización ARL')
    ccf_rate = fields.Float(string='Tarifa CCF')
    ccf_cot = fields.Float(string='Cotización CCF')
    arl_code = fields.Char(string='Código ARL')
    arl_risk = fields.Char(string='Clase de riesgo')

    sena_rate = fields.Float(string='Tarifa SENA')
    sena_cot = fields.Float(string='Cotización SENA')
    icbf_rate = fields.Float(string='Tarifa ICBF')
    icbf_cot = fields.Float(string='Cotización ICBF')
    esap_rate = fields.Float(string='Tarifa ESAP')
    esap_cot = fields.Float(string='Cotización ESAP')
    men_rate = fields.Float(string='Tarifa MEN')
    men_cot = fields.Float(string='Cotización MEN')
    exonerated = fields.Boolean(default=False, string='Exonerado de aportes')

    # FECHAS
    k_start = fields.Date(string='Fecha de ingreso')
    k_end = fields.Date(string='Fecha de retiro')
    vsp_start = fields.Date(string='Fecha de inicio de VSP')
    sln_start = fields.Date(string='Inicio licencia no remunerada')
    sln_end = fields.Date(string='Fin licencia no remunerada')
    ige_start = fields.Date(string='Inicio incapacidad')
    ige_end = fields.Date(string='Fin incapacidad')
    lma_start = fields.Date(string='Inicio licencia')
    lma_end = fields.Date(string='Fin licencia')
    vac_start = fields.Date(string='Inicio vacaciones')
    vac_end = fields.Date(string='Fin vacaciones')
    vct_start = fields.Date(string='Inicio centro de trabajo')
    vct_end = fields.Date(string='Fin centro de trabajo')
    atep_start = fields.Date(string='Inicio AT/EP')
    atep_end = fields.Date(string='Fin AT/EP')
