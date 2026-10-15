# -*- coding: utf-8 -*-
from odoo import models, fields, api
import unicodedata
import re


class HrPayslipReportLine(models.Model):
    _name = 'hr.payslip.report.line'
    _description = 'Línea de reporte de nómina'

    report_id = fields.Many2one(
        comodel_name='hr.payslip.report.setting',
        string='Plantilla'
    )
    name = fields.Char(
        string='Nombre',
        required=True
    )
    alias = fields.Char(
        string='Alias',
        compute='_compute_alias',
        store=True
    )
    is_basic = fields.Boolean(
        string='¿Básico?'
    )
    int = fields.Boolean(
        string='Integral'
    )
    sen_ele = fields.Boolean(
        string='Sena Lectiva'
    )
    sen_prod = fields.Boolean(
        string='Sena Productiva'
    )
    line_type = fields.Selection(
        selection=[
            ('earning', 'Devengo'),
            ('deduction', 'Deducción'),
            ('net', 'Neto')
        ],
        string='Tipo de línea'
    )
    concepts_ids = fields.Many2many(
        comodel_name='income.and.withholding.concepts',
        relation='concepts_line_report_rel',
        domain="[('company_id', '=', company_id)]", string='Conceptos'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        string='Compañía')

    @api.depends('name')
    def _compute_alias(self):
        for record in self:
            if record.name:
                alias = unicodedata.normalize('NFKD', record.name).encode('ASCII', 'ignore').decode('utf-8')
                alias = alias.lower()
                alias = re.sub(r'[^a-z0-9_]', '_', alias)
                record.alias = alias + '_' + str(record.id)
            else:
                record.alias = ''
