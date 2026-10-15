# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HrPayslipLine(models.Model):
    _name = 'hr.payslip.line.log'
    _description = 'Log de Linea de Nómina'

    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nómina', index=True
    )
    line_id = fields.Many2one(
        comodel_name='hr.payslip.line', string='Línea de Nómina', index=True
    )
    date_from = fields.Date(
        string='Fecha Inicio'
    )
    date_to = fields.Date(
        string='Fecha Fin'
    )
    no_pay_leave_days = fields.Float(
        string='Ausencias no Pagadas',
    )
    paternal_license_days = fields.Float(
        string='Días de Licencia de Partenidad/Maternidad',
    )
    worked_days = fields.Float(
        string='Días Tabajados'
    )
    total_salary = fields.Float(
        string='Salario Total'
    )
    total_earnings = fields.Float(
        string='Total Devengado'
    )
    total_comp_earnings = fields.Float(
        string='Total Ingresos Complementarios'
    )
    total_o_salarial_earnings = fields.Float(
        string='Total Otros Devengos Salariales'
    )
    total_o_rights = fields.Float(
        string='Total Otros Derechos'
    )
    total_o_earnings = fields.Float(
        string='Total Otros Devengos'
    )
    total_variable = fields.Float(
        string='Total Sueldo Variable'
    )
    total_subsidy = fields.Float(
        string='Total Subsidio Transporte/Conectividad'
    )
    total_base = fields.Float(
        string='Base'
    )
    total = fields.Float(
        string='Total'
    )
    concept_id = fields.Many2one(
        comodel_name='hr.concept', string='Concepto'
    )
    period_id = fields.Many2one(
        comodel_name='hr.period',
        string='Periodo'
    )
    payslip_processing_id = fields.Many2one(
        comodel_name='hr.payslip.processing',
        string='Procesamiento de Nómina'
    )
    amount_average_day = fields.Float(
        string='Valor Promedio Día'
    )
    holidays_days_left = fields.Float(
        string='Días de Vacaciones Restantes'
    )
    contract_duration = fields.Float(
        string='Duración de Contrato'
    )
    contract_id = fields.Many2one(
        comodel_name='hr.contract',
        string='Contrato',
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Empleado'
    )
    ibd = fields.Float(
        string='IBD'
    )
    rate = fields.Float(
        string='Porcentaje'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía'
    )

    # ------------------------------
    # Campos para retencion en la fuente
    # ------------------------------

    rtefte_income_ext = fields.Float(string='Ingreso exento')
    rtefte_apply_procedure_2 = fields.Boolean(string='Procedimiento 2')
    rtefte_prima = fields.Float(string='Prima')
    rtefte_prima_liq = fields.Float(string='Prima Liquida')
    rtefte_total_income = fields.Float(string='Total Ingresos')
    rtefte_ded_pens = fields.Float(string='Deducción Pensión')
    rtefte_ded_eps = fields.Float(string='Deducción EPS')
    rtefte_fond_sol = fields.Float(string='Fondo de solidaridad')
    rtefte_fond_sub = fields.Float(string='Fondo de subsistencia')
    rtefte_total_nci = fields.Float(
        string='Total Deducciones No Constitutivas de Ingreso')
    rtefte_neto_income = fields.Float(string='Ingreso Neto')
    rtefte_current_year = fields.Integer(string='Año actual')
    rtefte_uvt = fields.Float(string='UVT')
    rtefte_deduction_dependents = fields.Float(string='Deducción Dependientes')
    rtefte_deduction_estate = fields.Float(string='Deducción Interes Vivienda')
    rtefte_deduction_healthcare = fields.Float(
        string='Deducción Medicina Prepagada')
    rtefte_deduction_icetex = fields.Float(string='Deducción Intereses ICETEX')
    rtefte_deduction_total = fields.Float(string='Total Deducciones')
    rtefte_avp = fields.Float(string='Aporte Voluntario Pensiones')
    rtefte_afc = fields.Float(
        string='Ahorro para el Fomento a la Construcción')
    rtefte_voluntary_contributions = fields.Float(
        string='Contribuciones Voluntarias')
    rtefte_annual_top25 = fields.Float(string='Límite Anual Top 25%')
    rtefte_top25_monthly = fields.Float(string='Top 25% Mensual')
    rtefte_top25_total = fields.Float(string='Top 25% Total')
    rtefte_annual_top40 = fields.Float(string='Límite Anual Top 40%')
    rtefte_top40_monthly = fields.Float(string='Top 40% Mensual')
    rtefte_top40_total = fields.Float(string='Top 40% Total')
    rtefte_exempt_rent = fields.Float(string='Renta Exenta')
