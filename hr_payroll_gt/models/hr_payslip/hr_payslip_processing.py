# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrPayslipProcessing(models.Model):
    _inherit = 'hr.payslip.processing'

    def compute_payslips_ids_gt(self):
        for record in self:
            if not record.payslips_ids:
                raise ValidationError(
                    "No hay nóminas que calcular, debe crearlas primero")
            for payslip in record.payslips_ids:
                if payslip.period_id.id != record.period_id.id or \
                        payslip.payslip_type_id.id != record.payslip_type_id.id:
                    raise ValidationError(
                        'Las nómina del procesamiento de nómina deben tener el mismo periodo y mismo tipo de nómina')
                if not payslip.location_code:
                    payslip.location_code = record.company_id.chart_template
            record.error_log = record.payslips_ids.compute_slip_gt()

    def to_paid_gt(self):
        for record in self:
            record.payslips_ids.to_paid_gt()
            record.state = 'paid'
