# -*- coding: utf-8 -*-
"""Evaluación cualitativa de Class Performance (subtarea 8, 2.4 y 2.8.11).

Cuando una Actividad asignada corresponde al Componente marcado "Es Class
Performance" de una estructura de calificación avanzada, el docente no
registra un puntaje numérico directamente: selecciona, por cada criterio
activo de la Escala, una valoración cualitativa (Excellent, Very Good...).
El sistema convierte automáticamente esas valoraciones a su equivalencia
cuantitativa configurada (wk.school.colombo.grade.scale.rating) y traslada
el promedio a "Puntaje obtenido" (wk.student.assignment.marks_obtained,
ver models/grade_assignment.py), el mismo campo que usan los componentes
cuantitativos para el consolidado -ningún campo nuevo para el cálculo-.
"""
from odoo import api, fields, models


class CpEvaluationLine(models.Model):
    """Una fila = un criterio calificado para la Actividad de un estudiante."""

    _name = 'wk.school.colombo.cp.evaluation.line'
    _description = "Línea de evaluación de Class Performance"
    _order = 'sequence, id'

    student_assignment_id = fields.Many2one(
        'wk.student.assignment', string="Actividad del estudiante",
        required=True, ondelete='cascade')
    sequence = fields.Integer(related='criterion_id.sequence', store=True)
    criterion_id = fields.Many2one(
        'wk.school.colombo.grade.scale.cp.criterion', string="Criterio",
        required=True)
    scale_id = fields.Many2one(
        'wk.grade.scales', related='student_assignment_id.grading_scale_id',
        store=True)
    rating_id = fields.Many2one(
        'wk.school.colombo.grade.scale.rating', string="Valoración",
        domain="[('scale_id', '=', scale_id)]")
    value = fields.Float(
        string="Valor cuantitativo", related='rating_id.value', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.student_assignment_id._wk_recompute_cp_grade()
        return lines

    def write(self, vals):
        if 'rating_id' in vals:
            self.student_assignment_id._wk_check_grades_not_locked()
        res = super().write(vals)
        if 'rating_id' in vals:
            self.student_assignment_id._wk_recompute_cp_grade()
        return res

    def unlink(self):
        assignments = self.student_assignment_id
        res = super().unlink()
        assignments._wk_recompute_cp_grade()
        return res
