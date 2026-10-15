# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError


class EvaluationWizard(models.TransientModel):
    """Asistente "Evaluación de tareas" (tarea 11156).

    El metodo original (wk_school_management/wizard/evaluation_wizard.py::
    submit_score, Webkul v5.0.4) exige que toda asignacion individual en
    estado ``new`` haya sido enviada desde el portal y, si no, aborta con
    "No evaluation done because assignment is yet to be submitted!". Eso
    impide calificar actividades presenciales (examenes orales, sustentaciones,
    participacion en clase) que nunca reciben una entrega digital.

    Cuando la actividad tiene activado "Permitir evaluación sin entrega
    digital" se omite unicamente esa validacion: las lineas calificadas pasan
    de ``new`` a ``evaluate`` y las que el docente no califico se quedan como
    estan, sin nota automatica ni entrega ficticia. Con el interruptor
    desactivado se delega en el metodo original, de modo que el flujo estandar
    Nuevo -> Enviado -> Evaluado queda intacto.
    """

    _inherit = 'wk.evaluation.wizard'

    allow_eval_without_submission = fields.Boolean(
        string="Permitir evaluación sin entrega digital",
        related='assignment_id.allow_eval_without_submission')

    # Requerimiento "Estructura de calificación avanzada" (2.8): se usa en
    # la vista (wizard/evaluation_wizard_view.xml) para ocultar los campos
    # de conversión por rangos de la Escala estándar -el cálculo ya no
    # depende de ellos para una estructura avanzada, ver
    # models/grade_assignment.py::onchange_marks_obtained-.
    grading_scale_id = fields.Many2one(
        'wk.grade.scales', string="Estructura de calificación",
        related='class_assignment_id.grading_scale_id')

    def _wk_get_evaluated_assignments(self):
        """Devuelve las asignaciones individuales sobre las que opera el envio.

        Replica la seleccion del metodo original (el contexto de la accion) y
        agrega un respaldo con las lineas del asistente cuando el asistente se
        abre sin ``active_model``.
        """
        self.ensure_one()
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []

        if active_model == 'wk.student.assignment':
            return self.env[active_model].browse(active_ids)
        if active_model == 'wk.class.assignment':
            return self.env[active_model].browse(active_ids).student_assignment_ids
        return self.student_assignment_ids

    def _wk_is_scored(self, student):
        """Indica si el docente registro una calificacion en la linea."""
        return bool(student.exempted
                    or student.marks_obtained > 0
                    or student.point_obtained > 0)

    def _wk_apply_lowest_score(self, student):
        """Asigna la calificacion mas baja de la escala, como el metodo base."""
        scale_line = self.env['wk.grade.scale.line'].search(
            [('scale_id', '=', self.scale_id.id)], order='min_percent', limit=1)
        if not scale_line:
            return
        percent = scale_line.conversion_percent
        student.write({
            'scale_line_id': scale_line.id,
            'marks_obtained': (percent * self.total_marks) / 100,
            'point_obtained': scale_line.points,
            'percent_obtained': percent,
            'state': 'evaluate',
        })

    def submit_score(self):
        self.ensure_one()
        if not self.allow_eval_without_submission:
            return super().submit_score()

        student_assignments = self._wk_get_evaluated_assignments()

        if not self.student_assignment_ids:
            raise UserError(_('No assignments selected for evaluation!'))

        for student in student_assignments:
            if student.state == 'submit':
                if student.point_obtained > 0:
                    student.state = 'evaluate'
                if student.exempted:
                    student.state = 'evaluate'

            elif student.state == 'new':
                if self._wk_is_scored(student):
                    # Nuevo -> Evaluado directo, sin exigir la entrega previa.
                    student.state = 'evaluate'
                elif self.lowest_score:
                    # Solo para quienes no tienen nota manual, para no pisar lo
                    # que el docente acaba de registrar en el asistente.
                    self._wk_apply_lowest_score(student)
