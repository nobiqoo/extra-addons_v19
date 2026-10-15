# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrNoveltyType(models.Model):
    _inherit = 'hr.novelty.type'

    is_teacher_hours = fields.Boolean(
        string='Horas de profesor',
        help='Marca la categoría de novedad con la que se cargan las horas '
             'aprobadas de los profesores desde el módulo académico.')


class HrNovelty(models.Model):
    _inherit = 'hr.novelty'

    teacher_hour_line_ids = fields.One2many(
        comodel_name='hr.novelty.teacher.hour', inverse_name='novelty_id',
        string='Horas por Curso')
    is_teacher_hours = fields.Boolean(
        related='novelty_type_id.is_teacher_hours', store=True)
    teacher_total_hours = fields.Float(
        string='Total Horas', compute='_compute_teacher_totals', store=True)

    @api.depends('teacher_hour_line_ids.hours')
    def _compute_teacher_totals(self):
        for record in self:
            record.teacher_total_hours = sum(
                record.teacher_hour_line_ids.mapped('hours'))

    def update_teacher_amount(self):
        """Lleva al valor de la novedad la suma de las horas por curso."""
        for record in self.filtered(lambda n: n.state == 'draft'):
            record.amount = sum(
                record.teacher_hour_line_ids.mapped('subtotal'))

    def get_teacher_analytic_distribution(self):
        """Matriz de porcentajes por curso de las horas del mes.

        Devuelve {id de cuenta analítica: porcentaje}, agrupando los cursos
        que comparten cuenta. El porcentaje es el peso de las horas de cada
        curso sobre el total de horas de las novedades, así que también
        suma 100 cuando el mes tiene más de una novedad.
        """
        lines = self.mapped('teacher_hour_line_ids')
        total_hours = sum(lines.mapped('hours'))
        distribution = {}
        if not total_hours:
            return distribution
        for line in lines:
            key = line.analytic_account_id.id
            distribution[key] = (distribution.get(key, 0.0)
                                 + line.hours * 100 / total_hours)
        return distribution

    def to_confirm(self):
        for record in self.filtered('is_teacher_hours'):
            if not record.teacher_hour_line_ids:
                raise ValidationError(
                    f'La novedad {record.name} no tiene horas por curso.')
        return super().to_confirm()

    def unlink(self):
        self.mapped('teacher_hour_line_ids.attendance_ids').write(
            {'payroll_novelty_line_id': False})
        return super().unlink()
