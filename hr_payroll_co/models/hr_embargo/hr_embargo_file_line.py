# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrEmbargoFileLine(models.Model):
    _name = 'hr.embargo.file.line'
    _description = 'Judicial Deposit Flat File Line'
    _order = 'id'

    file_id = fields.Many2one(
        comodel_name='hr.embargo.file', string='File', required=True, ondelete='cascade')
    embargo_line_id = fields.Many2one(
        comodel_name='hr.embargo.line', string='Installment', required=True)
    embargo_id = fields.Many2one(
        comodel_name='hr.embargo', string='Garnishment',
        related='embargo_line_id.embargo_id', store=True)
    employee_id = fields.Many2one(
        comodel_name='hr.employee', string='Employee',
        related='embargo_id.employee_id', store=True)
    amount = fields.Float(
        string='Amount', related='embargo_line_id.amount', store=True)
    work_phone = fields.Char(string='Work Phone', compute='_compute_employee_info')
    work_email = fields.Char(string='Work Email', compute='_compute_employee_info')
    department_id = fields.Many2one(
        comodel_name='hr.department', string='Department', compute='_compute_employee_info')
    job_id = fields.Many2one(
        comodel_name='hr.job', string='Job Position', compute='_compute_employee_info')

    _file_id_embargo_line_id_uniq = models.Constraint(
        'UNIQUE (file_id, embargo_line_id)',
        'This installment is already included in this file.',
    )

    @api.depends('employee_id')
    def _compute_employee_info(self):
        for record in self:
            record.work_phone = record.employee_id.work_phone
            record.work_email = record.employee_id.work_email
            record.department_id = record.employee_id.department_id
            record.job_id = record.employee_id.job_id
