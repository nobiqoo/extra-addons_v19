# -*- coding: utf-8 -*-
from odoo import models, fields

STATE = [
    ('validated', 'Validated'),
    ('paid', 'Paid'),
]


class HrEmbargoLine(models.Model):
    _name = 'hr.embargo.line'
    _description = 'Garnishment Installment'
    _order = 'period_id'

    embargo_id = fields.Many2one(
        comodel_name='hr.embargo', string='Garnishment', required=True, ondelete='cascade')
    payslip_id = fields.Many2one(comodel_name='hr.payslip', string='Payslip')
    contract_id = fields.Many2one(
        string='Contract', related='embargo_id.contract_id', store=True)
    period_id = fields.Many2one(comodel_name='hr.period', string='Period')
    state = fields.Selection(string='Status', selection=STATE, default='validated')
    base_amount = fields.Float(string='Garnishable Base')
    amount = fields.Float(string='Installment Amount')

    def _compute_display_name(self):
        for record in self:
            record.display_name = f'{record.embargo_id.name} - {record.period_id.name}'
