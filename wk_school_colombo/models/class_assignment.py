# -*- coding: utf-8 -*-
"""Vínculo entre la clase ofertada y la estructura de calificación avanzada
(subtarea 8, requerimiento 2.6-2.7).

Cuando una Clase ofertada tiene una Escala de calificación avanzada
aplicada (wk.school.class.grading_scale_id, ver models/populate_class.py),
cada fila de "Tipos de actividad" (wk.class.assignment.type) queda
vinculada al Componente de calificación de origen del que se copió, y cada
Actividad asignada (wk.class.assignment) hereda ese mismo Componente -y, a
través de él, su tipo, sus pesos por corte y la Escala usada- sin que el
docente tenga que volver a configurarlo (ver wizard/assignment_wizard.py).
"""
from odoo import fields, models


class ClassAssignmentType(models.Model):
    """Fila de "Tipos de actividad" de la Clase ofertada (2.6)."""

    _inherit = 'wk.class.assignment.type'

    component_id = fields.Many2one(
        'wk.school.colombo.grade.scale.component', string="Componente de origen",
        help="Componente de la Escala de calificación avanzada del que se "
             "copió esta fila al presionar \"Aplicar estructura de "
             "calificación\". Vacío en una fila agregada manualmente (clase "
             "sin estructura avanzada aplicada).")
    weight_final = fields.Float(
        string="Peso Final (%)",
        help="Solo aplica con una Escala de 2 cortes: peso del componente "
             "dentro de Final. El campo estándar \"Weightage(%)\" se usa "
             "como el peso de Midterm (o el único peso, con 1 corte).")


class ClassAssignment(models.Model):
    """Actividad asignada: hereda el Componente de la estructura (2.7)."""

    _inherit = 'wk.class.assignment'

    component_id = fields.Many2one(
        'wk.school.colombo.grade.scale.component', string="Componente de evaluación",
        help="Se asigna una sola vez, desde el asistente \"Asignar tarea\", "
             "cuando la clase tiene una Escala de calificación avanzada "
             "aplicada, y ya no cambia después: tipo de actividad, corte, "
             "ponderación y Escala usada se leen siempre desde aquí, nunca "
             "se vuelven a pedir al docente.")
    grading_scale_id = fields.Many2one(
        'wk.grade.scales', string="Estructura de calificación",
        related='component_id.scale_id', store=True)
    weight_midterm = fields.Float(
        string="Peso Midterm (%)", related='component_id.weight', store=True)
    weight_final = fields.Float(
        string="Peso Final (%)", related='component_id.weight_final', store=True)
    is_class_performance = fields.Boolean(
        string="Es Class Performance",
        related='component_id.is_class_performance', store=True)

    def evaluate_assignment(self):
        """Incluye las asignaciones "Nuevo" cuando no exigen entrega previa.

        El método original (wk_school_management/models/class_assignment.py)
        solo precarga en el asistente las asignaciones en estado "submit",
        pensado para el flujo con entrega digital. Las actividades con
        "Permitir evaluación sin entrega digital" activo (tarea 11156,
        reutilizado aquí para toda actividad de una estructura avanzada,
        incluida Class Performance) nunca pasan por "submit": sin este
        ajuste, el asistente se abriría sin ningún estudiante para calificar.
        """
        self.ensure_one()
        action = super().evaluate_assignment()
        if self.assignment_id.allow_eval_without_submission and isinstance(action, dict):
            pending = self.student_assignment_ids.filtered(
                lambda sa: sa.state in ('new', 'submit'))
            context = dict(action.get('context') or {})
            context['default_student_assignment_ids'] = [(6, 0, pending.ids)]
            action['context'] = context
        return action
