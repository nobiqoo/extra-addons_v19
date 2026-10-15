# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from ..hr_payslip_noveltys.model_basic_payslip_novelty_type import CATEGORY_PAYSLIP

ORIGIN = [
    ('local', 'Local'),
    ('import', 'Importación')
]


class HrPayslipLine(models.Model):
    _name = 'hr.payslip.line'
    _description = 'Linea de Nómina'
    _order = 'name'

    name = fields.Char(string='Nombre')
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nómina', required=True, index=True)
    category = fields.Selection(
        string='Categoría', selection=CATEGORY_PAYSLIP, index=True)
    value = fields.Float(string='Valor')
    qty = fields.Float(string='Cantidad')
    rate = fields.Float(string='Porcentaje')
    total = fields.Float(string='Total')
    origin = fields.Selection(string='Origen', selection=ORIGIN)
    concept_id = fields.Many2one(
        comodel_name='hr.concept', string='Concepto', index=True)
    concept_code = fields.Char(
        string='Código del Concepto', related='concept_id.code', store=False)

    leave_id = fields.Many2one(
        comodel_name='hr.leave', string='Ausencia')
    novelty_id = fields.Many2one(
        comodel_name='hr.novelty', string='Novedad')
    overtime_id = fields.Many2one(
        comodel_name='hr.overtime', string='Hora Extra')
    log_ids = fields.One2many(
        comodel_name='hr.payslip.line.log', string='Logs', compute='_compute_log_ids'
    )
    is_rest_or_dayoff = fields.Boolean(string='Es día no habil')

    @api.depends('payslip_id.log_ids')
    def _compute_log_ids(self):
        for record in self:
            record.log_ids = record.payslip_id.log_ids.filtered(
                lambda x: x.concept_id.id == record.concept_id.id)

