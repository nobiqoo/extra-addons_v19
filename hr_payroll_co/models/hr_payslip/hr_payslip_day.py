# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

DAY_TYPE = [
    ('W', 'Trabajado'),
    ('A', 'Ausencia'),
    ('X', 'Sin contrato'),
]


class HrPayslipDay(models.Model):
    _name = 'hr.payslip.day'
    _description = 'Días de Nómina'
    _order = 'day'

    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nómina', required=True, index=True)
    day_type = fields.Selection(string='Tipo', selection=DAY_TYPE)
    day = fields.Integer(string='Día')
    name = fields.Char(string='Nombre', compute="_compute_name")

    @api.depends('day', 'day_type')
    def _compute_name(self):
        for record in self:
            record.name = str(record.day) + record.day_type
