# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AssignmentWizard(models.TransientModel):
    """Permite asignar actividades que inician y finalizan el mismo día.

    El asistente de Webkul (wk_school_management/wizard/assignment_wizard.py)
    obliga a que "No. de días" sea mayor que 0, de modo que la fecha límite
    siempre queda al menos un día después de la fecha de inicio. Eso impide
    programar actividades de corta duración que se realizan y evalúan dentro
    de la misma clase (cuestionarios, pruebas rápidas, evaluaciones orales,
    ejercicios prácticos) (tarea 11238).

    La validación de fechas del asistente (_check_for_assignment_duration) ya
    admite fechas iguales: solo bloquea cuando la fecha de inicio es posterior
    a la fecha límite, y esa restricción se conserva sin cambios, igual que la
    que exige que ambas fechas estén dentro de la duración del término.
    """

    _inherit = 'wk.assignment.wizard'

    # Requerimiento "Estructura de calificación avanzada" (2.7): cuando la
    # clase tiene una Escala avanzada aplicada, el campo "Actividad" pasa a
    # seleccionar un Componente de esa estructura en lugar de una Actividad
    # (wk.grade.assignment) aprobada -ver _onchange_component_id, que crea o
    # reutiliza esa plantilla por debajo, sin pedírselo al usuario-. La
    # vista (wizard/assignment_wizard_view.xml) oculta "Tipo"/"Actividad" y
    # muestra este campo en su lugar cuando grading_scale_id está presente.
    grading_scale_id = fields.Many2one(
        'wk.grade.scales', string="Escala de calificación",
        related='class_id.grading_scale_id')
    component_id = fields.Many2one(
        'wk.school.colombo.grade.scale.component', string="Actividad",
        domain="[('scale_id', '=', grading_scale_id), ('active', '=', True)]")

    @api.onchange('component_id')
    def _onchange_component_id(self):
        """Autocompleta tipo y plantilla a partir del Componente elegido.

        El docente no vuelve a parametrizar tipo de actividad, corte,
        ponderación ni Escala: todo se lee del Componente (requerimiento
        2.7). La plantilla (wk.grade.assignment) exigida por el campo
        ``assignment_id`` del asistente base se crea o se reutiliza aquí
        -una por Componente, nivel y materia-, aprobada y marcada "Permitir
        evaluación sin entrega digital" (ninguna actividad de una
        estructura avanzada pasa por el flujo de entrega del portal).
        """
        if not self.component_id:
            return
        component = self.component_id
        self.type_id = component.assignment_type_id
        if not self.total_marks:
            self.total_marks = 100

        Template = self.env['wk.grade.assignment']
        template = Template.search([
            ('grade_id', '=', self.grade_id.id),
            ('subject_id', '=', self.subject_id.id),
            ('type_id', '=', component.assignment_type_id.id),
            ('name', '=', component.name),
        ], limit=1)
        if not template:
            template = Template.create({
                'name': component.name,
                'grade_id': self.grade_id.id,
                'subject_id': self.subject_id.id,
                'type_id': component.assignment_type_id.id,
                'teacher_id': self.class_id.teacher_id.id,
                'state': 'approve',
                'allow_eval_without_submission': True,
            })
        elif template.state != 'approve':
            template.state = 'approve'
        self.assignment_id = template

    def assign_now(self):
        """Traslada el Componente elegido a la Actividad recién creada."""
        action = super().assign_now()
        if self.component_id and isinstance(action, dict) and action.get('res_id'):
            self.env['wk.class.assignment'].browse(action['res_id']).write({
                'component_id': self.component_id.id,
            })
        return action

    @api.constrains('no_of_days')
    def _check_no_of_days(self):
        """Admite duración de 0 días (actividad de un solo día).

        Reemplaza la validación original, que exigía ``no_of_days > 0``. Se
        mantiene el bloqueo para valores negativos, porque una duración
        negativa dejaría la fecha límite antes de la fecha de inicio.
        """
        for assignment in self:
            if assignment.no_of_days < 0:
                raise UserError(
                    _("The number of days for the assignment cannot be negative."))

    @api.onchange('start_date')
    def _onchange_assignment_start_date(self):
        """Recalcula la fecha límite al mover la fecha de inicio.

        El original lanza "Start date for assignment should be before the end
        date!!" cuando la nueva fecha de inicio supera la fecha límite vigente,
        antes de recalcularla. Con una actividad de un solo día (0 días) la
        fecha límite es igual a la de inicio, así que cualquier movimiento de
        la fecha de inicio hacia adelante disparaba el error y obligaba a
        capturar primero la fecha de finalización.

        Aquí se recalcula la fecha límite a partir de "No. de días", que nunca
        es negativo, por lo que la fecha límite resultante siempre es igual o
        posterior a la de inicio. No se altera lo que el docente escribió en
        "No. de días": la fecha límite ya se recalculaba así en el asistente
        original. La validación se conserva para el caso en que el recálculo no
        aplica, y las demás (fecha límite anterior al inicio al editarla, y
        duración dentro del término) siguen intactas.
        """
        if self.start_date and not self.env.context.get('assignment'):
            self.with_context(assignment=1).write({
                'end_date': self.start_date + timedelta(days=self.no_of_days)
            })
        elif self.start_date and self.end_date and self.start_date > self.end_date:
            raise UserError(
                _('Start date for assignment should be before the end date!!'))
