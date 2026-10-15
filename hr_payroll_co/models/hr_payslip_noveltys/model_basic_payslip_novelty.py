# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

STATE = [
    ('draft', 'Borrador'),
    ('confirm', 'Confirmada'),
    ('validated', 'Validada'),
    ('cancel', 'Cancelado'),
    ('paid', 'Pagada')
]


class ModelBasicPayslipNovelty(models.AbstractModel):
    _name = 'model.basic.payslip.novelty'
    _inherit = ['mail.thread']
    _description = 'model.basic.payslip.novelty'
    _order = 'name'

    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Selection(string='Estado', selection=STATE, default='draft')

    contract_id = fields.Many2one(comodel_name='hr.contract', string='Contrato',
                                  domain="[('state','=','open')]", required=True,
                                  index=True)
    employee_id = fields.Many2one(comodel_name='hr.employee',
                                  string='Empleado')

    approve_date = fields.Date(string='Fecha de aprobación')
    date_start = fields.Date(string='Fecha Inicio', required=True)
    date_end = fields.Date(string='Fecha Final')
    amount = fields.Float(string='Valor')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company, readonly=True)

    @api.onchange('contract_id')
    def _get_employee(self):
        for record in self:
            if record.contract_id:
                if not record.contract_id.employee_id:
                    raise ValidationError(
                        'El contrato %s no tiene un emplado relacionado' % self.contract_id.name)
                record.employee_id = record.contract_id.employee_id
            else:
                record.employee_id = False

    @api.onchange('employee_id')
    def _get_contract(self):
        for record in self:
            if not record.employee_id:
                record.contract_id = False
                continue
            contract_id = self.env['hr.contract'].search(
                [('employee_id', '=', record.employee_id.id), ('state', '=', 'open')])
            if not contract_id:
                raise ValidationError(
                    'El emplado %s no tiene contrato en proceso' % (record.employee_id.name))
            if len(contract_id) > 1:
                raise ValidationError('El emplado %s tiene %s contratos en proceso' % (
                    record.employee_id.name, len(contract_id)))
            record.contract_id = contract_id

    def to_cancel(self):
        for record in self:
            if record.state != 'paid':
                record.state = 'cancel'

    def to_draft(self):
        for record in self:
            if record.state != 'paid':
                record.state = 'draft'

    def to_confirm(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'confirm'

    def to_validated(self):
        for record in self:
            if record.state == 'confirm':
                record.state = 'validated'
