# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrOvertime(models.Model):
    _name = 'hr.overtime'
    _inherit = 'model.basic.payslip.novelty'
    _description = 'Hora Extra'
    _order = 'name'

    overtime_type_id = fields.Many2one(
        comodel_name='hr.overtime.type', string='Categoría Hora Extra', required=True)
    qty = fields.Float(string='Cantidad', required=True)
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nómina', readonly=True, index=True)
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo', readonly=True, index=True)
    amount = fields.Float(string='Valor', compute="_compute_value", store=True)
    rate = fields.Float(string='Factor', related='overtime_type_id.rate')
    overtime_sync_id = fields.Many2one(
        comodel_name='hr.overtime.sync', string='Sincronización', readonly=True, index=True, ondelete='set null')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'seq.hr.overtime') or ''
        return super(HrOvertime, self).create(vals_list)

    @api.depends('qty', 'rate', 'contract_id', 'date_start')
    def _compute_value(self):
        for record in filter(lambda x: x.state == 'draft', self):
            if not all((record.qty, record.rate, record.contract_id, record.date_start)):
                continue

            max_hours_work = self.env['economic.variable'].get_value_by_date(
                'MAX_HOURS_WORK', record.date_start)
            if max_hours_work == 0:
                raise ValidationError(
                    'Configure en las variables economicas "HORAS DE LA JORNADA LABORAL MAXIMA MENSUAL" para el año %s' % record.date_start.year)

            record._set_amount(max_hours_work)

    def _set_amount(self, max_hours_work):
        wage = self.contract_id.get_wage(self.date_start).get('wage', 0)
        self.amount = wage * self.rate * self.qty / max_hours_work

    def to_confirm(self):
        self._compute_value()
        return super(HrOvertime, self).to_confirm()

    def to_validated(self):
        period = self.env['hr.period']
        for record in self:
            if record.state != 'confirm':
                continue
            if not record.contract_id:
                raise ValidationError(
                    "Por favor defina el contrato de la hora extra")
            if not record.date_start:
                raise ValidationError(
                    "Por favor defina la fecha de la hora extra")
            record.period_id = period.get_period(
                record.date_start, False, record.contract_id.schedule_pay)
        return super(HrOvertime, self).to_validated()

    def create_payslip_line(self, payslip_id):
        overtime_type_id = self.overtime_type_id
        payslip_line = {
            'name': overtime_type_id.name,
            'payslip_id': payslip_id,
            'category': overtime_type_id.category,
            'value': self.amount,
            'qty': self.qty,
            'rate': 100,
            'total': self.amount,
            'origin': 'local',
            'concept_id': None,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': self.id,
        }
        for unique_key in ['rate', 'concept_id', 'leave_id', 'novelty_id', 'overtime_id']:
            if 'unique_key' in payslip_line:
                payslip_line['unique_key'] += str(payslip_line[unique_key])
            else:
                payslip_line['unique_key'] = str(payslip_line[unique_key])
        return payslip_line

    def belongs_category(self, categories):
        return self.overtime_type_id.id in categories
