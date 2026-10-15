# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


def _month_start(date_ref):
    return date_ref.replace(day=1)


def _month_end(date_ref):
    return _month_start(date_ref) + relativedelta(months=1, days=-1)


class TeacherHoursWizard(models.TransientModel):
    _name = 'teacher.hours.wizard'
    _description = 'Generar Novedades de Horas de Profesor'

    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: _month_start(fields.Date.context_today(self)))
    date_to = fields.Date(
        string='Hasta', required=True,
        default=lambda self: _month_end(fields.Date.context_today(self)))
    employee_ids = fields.Many2many(
        comodel_name='hr.employee', string='Profesores',
        help='Si se deja vacío se procesan todos los profesores con horas '
             'aprobadas en el rango.')
    novelty_type_id = fields.Many2one(
        comodel_name='hr.novelty.type', string='Categoría de Novedad',
        required=True, domain=[('is_teacher_hours', '=', True)],
        default=lambda self: self.env['hr.novelty.type'].search(
            [('is_teacher_hours', '=', True)], limit=1))
    company_id = fields.Many2one(
        comodel_name='res.company', string='Compañía',
        default=lambda self: self.env.company, required=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(
                    'La fecha inicial no puede ser mayor a la fecha final.')

    def _get_attendances(self):
        domain = [
            ('approved_for_payroll', '=', True),
            ('payroll_novelty_line_id', '=', False),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('employee_id.company_id', '=', self.company_id.id),
        ]
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        return self.env['hr.attendance'].search(domain)

    def action_generate(self):
        """Consolida las asistencias aprobadas que aún no están en una
        novedad. Al aprobar una asistencia sus horas ya se suman solas a la
        novedad del mes; el asistente recoge las que hayan quedado por fuera,
        por ejemplo las aprobadas antes de instalar el módulo."""
        self.ensure_one()
        attendances = self._get_attendances()
        if not attendances:
            raise ValidationError(
                'No hay asistencias aprobadas para nómina y sin consolidar en '
                'el rango seleccionado.')
        novelties = attendances._consolidate_payroll_hours(
            self.novelty_type_id.sudo())
        return {
            'type': 'ir.actions.act_window',
            'name': 'Novedades de Horas Generadas',
            'res_model': 'hr.novelty',
            'view_mode': 'list,form',
            'domain': [('id', 'in', novelties.ids)],
        }
