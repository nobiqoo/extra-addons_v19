# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class GradeAssignment(models.Model):
    """Actividad/tarea de calificacion (tarea 11156).

    Se agrega un interruptor por actividad para las evaluaciones que se
    realizan durante la clase (examenes orales, presentaciones, participacion,
    pruebas escritas fisicas) y que por lo tanto nunca reciben una entrega
    desde el portal del estudiante.
    """

    _inherit = 'wk.grade.assignment'

    allow_eval_without_submission = fields.Boolean(
        string="Permitir evaluación sin entrega digital",
        default=False,
        help="Permite que el docente califique la actividad aunque el "
             "estudiante no haya realizado una entrega desde el portal. "
             "La asignación individual pasa directamente de Nuevo a "
             "Evaluado. Si se desactiva, se conserva el flujo estándar "
             "Nuevo → Enviado → Evaluado.")


class StudentAssignment(models.Model):
    """Asignacion individual del estudiante (tarea 11156).

    El valor configurado en la actividad se traslada a cada linea mediante un
    related no almacenado, para poder condicionar fila por fila el modificador
    ``readonly`` de "Marcas obtenidas" dentro del asistente de evaluacion. No
    se almacena porque siempre debe reflejar el estado actual de la actividad:
    al desactivar el campo, las lineas existentes vuelven al comportamiento
    estandar sin necesidad de recalcular nada.
    """

    _inherit = 'wk.student.assignment'

    allow_eval_without_submission = fields.Boolean(
        string="Permitir evaluación sin entrega digital",
        related='assignment_id.allow_eval_without_submission')

    # Requerimiento "Estructura de calificación avanzada" (2.7, 2.8): estos
    # campos se leen siempre desde la Actividad asignada (class_assignment_id,
    # ver models/class_assignment.py), nunca se piden de nuevo al docente.
    component_id = fields.Many2one(
        'wk.school.colombo.grade.scale.component', string="Componente de evaluación",
        related='class_assignment_id.component_id', store=True)
    grading_scale_id = fields.Many2one(
        'wk.grade.scales', string="Estructura de calificación",
        related='class_assignment_id.grading_scale_id', store=True)
    weight_midterm = fields.Float(
        string="Peso Midterm (%)",
        related='class_assignment_id.weight_midterm', store=True)
    weight_final = fields.Float(
        string="Peso Final (%)",
        related='class_assignment_id.weight_final', store=True)
    is_class_performance = fields.Boolean(
        string="Es Class Performance",
        related='class_assignment_id.is_class_performance', store=True)
    cp_line_ids = fields.One2many(
        'wk.school.colombo.cp.evaluation.line', 'student_assignment_id',
        string="Evaluación de Class Performance")
    grades_locked_for_me = fields.Boolean(
        string="Edición bloqueada para mí", compute='_compute_grades_locked_for_me',
        help="Siempre False para Officer/Admin -nunca quedan bloqueados, "
             "requerimiento 2.10-. Para el docente, refleja si el "
             "Consolidado de la clase tiene la edición bloqueada o el "
             "corte Final ya confirmado.")

    def _compute_grades_locked_for_me(self):
        is_officer = self.env.user.has_group(
            'wk_school_management.wk_school_management_officer_group')
        if is_officer:
            self.grades_locked_for_me = False
            return
        Consolidated = self.env['wk.school.colombo.grade.consolidated'].sudo()
        for record in self:
            if not record.grading_scale_id:
                record.grades_locked_for_me = False
                continue
            consolidated = Consolidated.search(
                [('populate_class_id', '=', record.populate_class_id.id)], limit=1)
            record.grades_locked_for_me = bool(
                consolidated and (
                    consolidated.grades_locked
                    or consolidated.final_state == 'confirmed'))

    @api.model_create_multi
    def create(self, vals_list):
        """Precarga los criterios activos de Class Performance (2.4, 2.8.11).

        Una vez creada la línea, el docente solo elige la valoración de cada
        criterio -nunca registra ni calcula el resultado manualmente-.
        """
        records = super().create(vals_list)
        for record in records:
            if record.is_class_performance and not record.cp_line_ids:
                record._wk_seed_cp_lines()
        return records

    def write(self, vals):
        """Impide al docente modificar notas con el Consolidado bloqueado.

        Requerimiento "Confirmación, bloqueo de edición..." (2.10): mientras
        la edición esté bloqueada (wk.school.colombo.grade.consolidated.
        grades_locked) o el corte Final ya esté confirmado, el docente puede
        consultar pero no modificar; Officer/Admin nunca queda bloqueado.
        Solo aplica a Actividades de una estructura avanzada
        (grading_scale_id); el flujo estándar no se toca.
        """
        if {'marks_obtained', 'exempted', 'description', 'point_obtained'} & set(vals):
            self.filtered('grading_scale_id')._wk_check_grades_not_locked()
        return super().write(vals)

    def _wk_check_grades_not_locked(self):
        if self.env.context.get('skip_lock_check'):
            return
        if self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            return
        classes = self.mapped('populate_class_id')
        if not classes:
            return
        consolidated = self.env['wk.school.colombo.grade.consolidated'].sudo().search(
            [('populate_class_id', 'in', classes.ids)])
        blocked = consolidated.filtered(
            lambda c: c.grades_locked or c.final_state == 'confirmed')
        if blocked:
            raise UserError(_(
                "La edición de calificaciones está bloqueada para la clase "
                "\"%s\". Contacte a un usuario Officer/Admin para "
                "habilitarla.") % blocked[0].populate_class_id.display_name)

    def _wk_seed_cp_lines(self):
        """Crea una línea vacía por cada criterio activo de la Escala."""
        self.ensure_one()
        criteria = self.grading_scale_id.cp_criterion_ids.filtered('active')
        if criteria:
            self.cp_line_ids = [
                (0, 0, {'criterion_id': criterion.id})
                for criterion in criteria]

    def action_open_cp_form(self):
        """Abre la pantalla de evaluación por criterio de Class Performance.

        Botón de la lista de estudiantes del asistente "Evaluar" y de la
        pestaña "Students" de la Actividad asignada (requerimiento 2.8.11).
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Class Performance - %s") % self.student_id.display_name,
            'res_model': 'wk.student.assignment',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'wk_school_colombo.wk_student_assignment_cp_form').id, 'form')],
            'target': 'new',
        }

    def _wk_recompute_cp_grade(self):
        """Promedia las valoraciones calificadas y actualiza "Puntaje obtenido".

        Solo los criterios ya calificados (con Valoración) entran en el
        promedio; un criterio todavía sin calificar no cuenta como 0. El
        docente nunca calcula ni registra este resultado manualmente
        (requerimiento 2.8.11). Cuando los criterios activos quedan todos
        calificados, la actividad pasa a "Evaluado" automáticamente -mismo
        estado que usa el Consolidado (models/grade_consolidated.py) para
        reconocer que un componente ya tiene nota, sea cuantitativo o
        cualitativo-.
        """
        for record in self:
            if not record.is_class_performance:
                continue
            rated = record.cp_line_ids.filtered('rating_id')
            average = (sum(rated.mapped('value')) / len(rated)) if rated else 0.0
            vals = {'marks_obtained': average}
            if (record.cp_line_ids and len(rated) == len(record.cp_line_ids)
                    and record.state != 'evaluate'):
                vals['state'] = 'evaluate'
            # skip_lock_check: esta escritura es consecuencia de calificar un
            # criterio en wk.school.colombo.cp.evaluation.line, que ya validó
            # el bloqueo por su cuenta (models/class_performance.py); no se
            # vuelve a exigir aquí.
            record.with_context(evaluate=1, skip_lock_check=1).write(vals)

    @api.onchange('marks_obtained')
    def onchange_marks_obtained(self):
        """Para estructuras de calificación avanzada, omite la conversión
        por rangos de la Escala estándar (2.8).

        El puntaje registrado por el docente -o calculado por el sistema
        para Class Performance, ver _wk_recompute_cp_grade- es el valor
        académico directo del componente: no debe convertirse mediante los
        tramos de la Escala estándar (scale_line_id/percent_obtained), que
        para estas estructuras ni siquiera participan en el cálculo.
        """
        if self.grading_scale_id:
            if self.total_marks and self.marks_obtained > self.total_marks:
                raise ValidationError(
                    _('Marks obtained cannot be greater than Total Marks.'))
            return
        return super().onchange_marks_obtained()
