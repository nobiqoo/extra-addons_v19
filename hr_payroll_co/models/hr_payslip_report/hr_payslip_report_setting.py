# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrPayslipReportSetting(models.Model):
    _name = 'hr.payslip.report.setting'
    _description = 'Configuración de reporte de nómina'

    name = fields.Char(
        string='Nombre')

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        string='Compañía')

    # Devengos

    basic_salary = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_basic_salary_rel',
        domain="[('company_id', '=', company_id)]", string='Salario Básico')

    basic_salary_int = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_basic_salary_int_rel',
        domain="[('company_id', '=', company_id)]", string='Salario Básico Integral')

    elective_support_fee = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_elective_support_fee_rel',
        domain="[('company_id', '=', company_id)]", string='Cuota de sostenimiento electivo')

    elective_prod_fee = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_elective_prod_fee_rel',
        domain="[('company_id', '=', company_id)]", string='Cuota de sostenimiento productivo')

    transport_subsidy = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_transport_subsidy_rel',
        domain="[('company_id', '=', company_id)]", string='Subsidio de transporte')

    ces_liq = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_ces_liq_rel',
        domain="[('company_id', '=', company_id)]", string='Cesantias Liquidación')

    compensation = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_compensation_rel',
        domain="[('company_id', '=', company_id)]", string='Indemnización')

    int_ces_liq = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_int_ces_liq_rel',
        domain="[('company_id', '=', company_id)]", string='Intereses de Cesantias Liquidación')

    family_day = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_family_day_rel',
        domain="[('company_id', '=', company_id)]", string='Día de la Familia')

    general_illness = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_general_illness_rel',
        domain="[('company_id', '=', company_id)]", string='Incapacidad Enfermedad General')

    mat_license = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_mat_license_rel',
        domain="[('company_id', '=', company_id)]", string='Licencia de Maternidad')

    prima_liq = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_prima_liq_rel',
        domain="[('company_id', '=', company_id)]", string='Prima Liquidación')
    
    vac_non_working = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_vac_non_working_rel',
        domain="[('company_id', '=', company_id)]", string='Vacaciones no Habiles')

    vac_enjoy = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_vac_enjoy_rel',
        domain="[('company_id', '=', company_id)]", string='Vacaciones Disfrutadas')

    vac_liq = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_vac_liq_rel',
        domain="[('company_id', '=', company_id)]", string='Vacaciones Liquidación')

    aux_extra = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_aux_extra_rel',
        domain="[('company_id', '=', company_id)]", string='Auxilio Extralegal de Transporte no Constituivo de Salario')

    bono_no_const = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_bono_no_const_rel',
        domain="[('company_id', '=', company_id)]", string='Bono no Constitutivo de Salario')

    # Deducciones

    voluntary_saving_future = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_voluntary_saving_future_rel',
        domain="[('company_id', '=', company_id)]", string='Ahorro Voluntario - DAFUTURO')

    voluntary_saving_pension_future = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_voluntary_saving_pension_future_rel',
        domain="[('company_id', '=', company_id)]", string='Ahorro Voluntario a Pensión - DAFUTURO')

    voluntary_saving_pension_skandia = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_voluntary_saving_pension_skandia_rel',
        domain="[('company_id', '=', company_id)]", string='Ahorro Voluntario a Pensión - SKANDIA')

    saving_afc_boc = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_saving_afc_boc_rel',
        domain="[('company_id', '=', company_id)]", string='Ahorro Voluntario AFC - Banco de Occidente')

    saving_afc_bco = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_saving_afc_bco_rel',
        domain="[('company_id', '=', company_id)]", string='Ahorro Voluntario AFC - Bancolombia')

    saving_afc_dvi = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_saving_afc_dvi_rel',
        domain="[('company_id', '=', company_id)]", string='Ahorro Voluntario AFC - Davivienda')

    ded_pen = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_ded_pen_rel',
        domain="[('company_id', '=', company_id)]", string='Deducción Pensión')

    ded_eps = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_ded_eps_rel',
        domain="[('company_id', '=', company_id)]", string='Deducción Salud')

    ded_solidary = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_ded_solidary_rel',
        domain="[('company_id', '=', company_id)]", string='Fondo de Solidaridad')

    ded_subsistence = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_ded_subsistence_rel',
        domain="[('company_id', '=', company_id)]", string='Fondo de Subsistencia')

    lib_compensar = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_lib_compensar_rel',
        domain="[('company_id', '=', company_id)]", string='Libranza Compensar')

    medicine_pre_col = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_medicine_pre_col_rel',
        domain="[('company_id', '=', company_id)]", string='Medicina Prepagada Colsanitas')

    medicine_pre_med = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_medicine_pre_med_rel',
        domain="[('company_id', '=', company_id)]", string='Medicina Prepagada Medisanitas')

    plan_esp_col = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_plan_esp_col_rel',
        domain="[('company_id', '=', company_id)]", string='Plan Especial Colsanitas')

    ded_rete = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_ded_rete_rel',
        domain="[('company_id', '=', company_id)]", string='Retención en la Fuente')

    # Netos

    nets = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='hr_report_nets_rel',
        domain="[('company_id', '=', company_id)]", string='Netos')

    # Lines

    earning_lines_ids = fields.One2many(
        comodel_name='hr.payslip.report.line',
        string='Devengos',
        domain=[('line_type', '=', 'earning')],
        inverse_name='report_id',
    )
    deduction_lines_ids = fields.One2many(
        comodel_name='hr.payslip.report.line',
        string='Deducciones',
        domain=[('line_type', '=', 'deduction')],
        inverse_name='report_id',
    )
    net_lines_ids = fields.One2many(
        comodel_name='hr.payslip.report.line',
        string='Netos',
        domain=[('line_type', '=', 'net')],
        inverse_name='report_id',
    )

    @api.depends('company_id', 'name')
    def _compute_display_name(self):
        if len(self) == 1:
            self.env['income.and.withholding.concepts'].load()
        for record in self:
            record.display_name = record.name or '/'
