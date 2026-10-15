# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrNoveltyTeacherHour(models.Model):
    _name = 'hr.novelty.teacher.hour'
    _description = 'Horas de Profesor por Curso'
    _order = 'novelty_id, school_class_id'

    novelty_id = fields.Many2one(
        comodel_name='hr.novelty', string='Novedad', required=True,
        ondelete='cascade', index=True)
    school_class_id = fields.Many2one(
        comodel_name='wk.school.class', string='Curso', required=True)
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account', string='Cuenta Analítica',
        required=True)
    hours = fields.Float(
        string='Horas', required=True,
        help='Suma de las horas aprobadas para este curso en el mes.')
    hour_value = fields.Float(
        string='Valor Hora',
        help='Valor hora vigente del contrato en el mes liquidado.')
    subtotal = fields.Monetary(
        string='Subtotal', compute='_compute_subtotal', store=True,
        currency_field='currency_id')
    percentage = fields.Float(
        string='Distribución (%)', compute='_compute_percentage', store=True,
        digits=(5, 2),
        help='Peso del curso sobre el total de horas del mes. Es la '
             'distribución analítica con la que se contabiliza la nómina.')
    attendance_ids = fields.One2many(
        comodel_name='hr.attendance', inverse_name='payroll_novelty_line_id',
        string='Asistencias', readonly=True)
    currency_id = fields.Many2one(
        related='novelty_id.company_id.currency_id', readonly=True)
    state = fields.Selection(related='novelty_id.state', store=True)
    contract_id = fields.Many2one(
        related='novelty_id.contract_id', store=True, index=True,
        string='Contrato')
    date = fields.Date(
        related='novelty_id.date_start', store=True, string='Periodo',
        help='Último día del mes en el que se dictaron las horas.')
    payroll_state = fields.Selection(
        selection=[('pending', 'Pendiente'), ('paid', 'Pagado')],
        string='Estado', compute='_compute_payroll_state', store=True,
        help='Pagado cuando la nómina que incluye estas horas está pagada.')

    @api.depends('novelty_id.state')
    def _compute_payroll_state(self):
        for record in self:
            record.payroll_state = (
                'paid' if record.novelty_id.state == 'paid' else 'pending')

    def _sync_hours(self):
        """Las horas de la línea son la suma de las asistencias aprobadas
        que tiene consolidadas."""
        for record in self:
            hours = sum(record.attendance_ids.mapped('payroll_hours'))
            if hours != record.hours:
                record.hours = hours

    @api.depends('hours', 'hour_value')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.hours * record.hour_value

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('novelty_id').update_teacher_amount()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'hours', 'hour_value'} & set(vals):
            self.mapped('novelty_id').update_teacher_amount()
        return res

    def unlink(self):
        novelties = self.mapped('novelty_id')
        self.attendance_ids.write({'payroll_novelty_line_id': False})
        res = super().unlink()
        novelties.update_teacher_amount()
        return res

    @api.depends('hours', 'novelty_id.teacher_hour_line_ids.hours')
    def _compute_percentage(self):
        for record in self:
            total_hours = sum(record.novelty_id.teacher_hour_line_ids.mapped(
                'hours'))
            record.percentage = (
                record.hours * 100 / total_hours) if total_hours else 0.0
