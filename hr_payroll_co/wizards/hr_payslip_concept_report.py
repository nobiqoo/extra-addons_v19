# -*- coding: utf-8 -*-
from odoo import models, fields
from ..models.hr_payslip.hr_payslip import STATE
from ..models.hr_payslip_noveltys.model_basic_payslip_novelty_type import CATEGORY_PAYSLIP


class HrPayslipConceptReport(models.Model):
    _name = "hr.payslip.concept.report"
    _description = "Reporte de conceptos de nómina"

    user_id = fields.Many2one(comodel_name='res.users', string='Usuario')
    company_id = fields.Many2one(comodel_name="res.company", string='Compañia')

    employee = fields.Char(string='Empleado')
    employee_id = fields.Char(string='ID de empleado')
    vat = fields.Char(string='Número de identificación')
    contract = fields.Char(string='Contrato')
    contract_id = fields.Char(string='ID de contrato')
    contract_group = fields.Char(string='Grupo de contrato')
    contract_date_start = fields.Date(string='Inicio de contrato')
    contract_settlement_date = fields.Date(string='Liquidación de contrato')
    contract_schedule_pay = fields.Char(string='Pago')
    contract_wage = fields.Float(string='Salario')

    payslip_type = fields.Char(string='Tipo de nómina')
    payslip_period = fields.Char(string='Periodo de nómina')
    payslip_liquidation_date = fields.Date(string='Liquidación de nómina')
    payslip_accounting_date = fields.Date(string='Contabilización de nómina')
    payslip_state = fields.Selection(string='Estado de nómina', selection=STATE)

    payslip_line = fields.Char(string='Concepto')
    payslip_category = fields.Selection(string='Categoría de concepto', selection=CATEGORY_PAYSLIP + [('no_category', 'Sin categoría')])
    payslip_line_qty = fields.Float(string='Cantidad')
    payslip_line_value = fields.Float(string='Valor')
    payslip_line_total = fields.Float(string='Total')

    novelty = fields.Char(string='Novedad')
    novelty_type = fields.Char(string='Categoría de novedad')

    leave = fields.Char(string='Ausencia')
    code_cie10 = fields.Char(string='Código CIE10')
    description_cie10 = fields.Char(string='Descripción del diagnóstico')
    leave_actual_start_date = fields.Date(string='Fecha Real de Inicio')
    leave_actual_end_date = fields.Date(string='Fecha Real de Fin')
    leave_type = fields.Char(string='Categoría de ausencia')
    leave_date_start = fields.Date(string='Inicio de ausencia')
    leave_date_end = fields.Date(string='Fin de ausencia')

    overtime = fields.Char(string='Hora extra')
    overtime_type = fields.Char(string='Categoría de hora extra')

    bank_id = fields.Many2one(comodel_name='res.bank', string='Banco')
    bank_account = fields.Char(string='Número de cuenta bancaria')
    l10n_latam_identification_type_id = fields.Many2one(comodel_name='l10n_latam.identification.type', string="Tipo de Documento", required=True)
    concept_id = fields.Many2one(comodel_name='hr.concept', string='Concepto de la Ausencia')
