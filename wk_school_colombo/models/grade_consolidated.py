# -*- coding: utf-8 -*-
"""Consolidado de notas por clase (subtarea 8, requerimiento 2.9-2.10).

Un registro de ``wk.school.colombo.grade.consolidated`` por Clase ofertada
con una Escala de calificación avanzada aplicada (ver
models/populate_class.py::action_apply_grading_structure, que crea este
registro junto con una línea por cada estudiante matriculado). El
consolidado se alimenta automáticamente de las evaluaciones registradas en
las Actividades asignadas (wk.class.assignment / wk.student.assignment) y
de las horas de ausencia acumuladas (models/class_attendance.py); el
usuario nunca registra una nota aquí.

Motor de cálculo (requerimiento 2.9.1/2.9.2): nota por componente = puntaje
obtenido directo (promedio si hay más de una actividad del mismo
componente); aporte = nota × peso/100; Midterm/Final Grade = suma de
aportes del corte correspondiente. Con 1 corte, el resultado único se
expone como Final Grade. Pass/Fail y el rango de desempeño se derivan de
la Final Grade y de la regla de ausencias configurada en la Escala.

Una vez confirmado un corte (grade.consolidated.midterm_state/final_state),
sus valores dejan de recalcularse: los cambios posteriores en la
estructura, ponderaciones o equivalencias no alteran resultados históricos
ya consolidados (requerimiento 2.2, 2.3, 2.5, 2.10).
"""
import base64
import csv
import io
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GradeConsolidated(models.Model):
    _name = 'wk.school.colombo.grade.consolidated'
    _description = "Consolidado de notas"
    _order = 'create_date desc'

    _class_uniq = models.Constraint(
        'unique(populate_class_id)',
        "Ya existe un Consolidado de notas para esta Clase ofertada.")

    populate_class_id = fields.Many2one(
        'wk.school.class', string="Clase ofertada", required=True,
        ondelete='cascade', index=True)
    is_active_class = fields.Boolean(
        related='populate_class_id.is_active_class', store=True,
        string="Clase activa")
    grading_scale_id = fields.Many2one(
        'wk.grade.scales', string="Estructura de calificación",
        related='populate_class_id.grading_scale_id', store=True)
    cuts_count = fields.Selection(
        related='grading_scale_id.cuts_count', store=True)
    grade_decimals = fields.Integer(
        related='grading_scale_id.grade_decimals', string="Decimales")
    allow_edit_confirmed = fields.Boolean(
        related='grading_scale_id.allow_edit_confirmed',
        string="Permite editar confirmadas")
    grade_id = fields.Many2one(
        related='populate_class_id.grade_id', store=True, string="Nivel")
    subject_id = fields.Many2one(
        related='populate_class_id.subject_id', store=True, string="Módulo")
    teacher_id = fields.Many2one(
        related='populate_class_id.teacher_id', store=True, string="Docente")
    academic_year_id = fields.Many2one(
        related='populate_class_id.academic_year_id', store=True,
        string="Periodo académico")
    program_type_id = fields.Many2one(
        related='grading_scale_id.program_type_id', store=True,
        string="Programa")
    modality = fields.Selection(
        related='grading_scale_id.modality', string="Modalidad")
    pass_grade = fields.Float(
        related='grading_scale_id.pass_grade', string="Nota mínima de aprobación")
    class_assignment_type_ids = fields.One2many(
        related='populate_class_id.class_assignment_type_ids',
        string="Ponderaciones de la clase")

    grades_locked = fields.Boolean(
        string="Edición de notas bloqueada al docente", default=False,
        help="Mientras esté desmarcado, el docente puede registrar o "
             "modificar calificaciones de la clase (según sus permisos). "
             "Marcado, puede consultarlas pero no modificarlas. No afecta "
             "la consulta ni edición de usuarios administrativos.")
    teacher_edit_enabled = fields.Boolean(
        string="Edición docente habilitada",
        compute='_compute_teacher_edit_enabled', inverse='_inverse_teacher_edit_enabled',
        help="Desmarcado: el docente puede consultar sus calificaciones "
             "pero no modificarlas (ni los criterios de Class Performance). "
             "Officer/Admin nunca queda bloqueado. Equivalente directo de "
             "\"Edición de notas bloqueada al docente\", solo que en "
             "sentido positivo.")
    confirmed_display = fields.Boolean(
        string="Calificaciones confirmadas", compute='_compute_confirmed_display',
        help="Indicador de solo lectura: el corte Final ya fue confirmado "
             "y quedó congelado como histórico académico. Para confirmar o "
             "reabrir, use los botones \"Confirmar Final\"/\"Reabrir "
             "Final\" -no es un check editable, porque saltarse esa "
             "validación rompería el histórico.")

    absence_rule_summary = fields.Char(
        string="Regla de ausencias", compute='_compute_absence_rule_summary')
    overall_state = fields.Selection([
        ('draft', 'Borrador'), ('in_progress', 'En proceso'),
        ('published', 'Publicada'),
    ], string="Estado", compute='_compute_overall_state', store=True)

    avg_final_grade = fields.Float(string="Promedio general", compute='_compute_stats')
    pass_count = fields.Integer(string="Aprobados", compute='_compute_stats')
    fail_count = fields.Integer(string="Reprobados", compute='_compute_stats')
    pending_count = fields.Integer(string="Pendientes", compute='_compute_stats')
    pass_pct = fields.Float(string="% Aprobados", compute='_compute_stats')
    fail_pct = fields.Float(string="% Reprobados", compute='_compute_stats')
    absence_alert_count = fields.Integer(
        string="Con ausencias > mínimo", compute='_compute_stats',
        help="Estudiantes cuyas horas de ausencia acumuladas ya superan "
             "las Horas mínimas configuradas en la Escala (aplica o no la "
             "regla de ausencias, según su Final Grade).")
    performance_distribution_summary = fields.Char(
        string="Distribución por desempeño", compute='_compute_stats')

    attendance_ids = fields.Many2many(
        'wk.student.class.attendance', compute='_compute_attendance_ids',
        string="Asistencia de la clase",
        help="Todas las líneas de asistencia de todas las sesiones de "
             "esta clase, de solo lectura -el detalle completo sigue "
             "viviendo en \"Marcar Asistencia\" de cada sesión-.")

    midterm_state = fields.Selection([
        ('draft', 'Borrador'), ('confirmed', 'Confirmado'),
    ], string="Estado Midterm", default='draft', required=True)
    midterm_confirmed_by = fields.Many2one('res.users', string="Confirmado por (Midterm)")
    midterm_confirmed_date = fields.Datetime(string="Fecha de confirmación (Midterm)")

    final_state = fields.Selection([
        ('draft', 'Borrador'), ('confirmed', 'Confirmado'),
    ], string="Estado Final", default='draft', required=True)
    final_confirmed_by = fields.Many2one('res.users', string="Confirmado por (Final)")
    final_confirmed_date = fields.Datetime(string="Fecha de confirmación (Final)")
    final_reopened_by = fields.Many2one(
        'res.users', string="Reabierto por (Final)",
        help="Trazabilidad de modificaciones posteriores a la confirmación "
             "(requerimiento 2.10): usuario y fecha de la última vez que se "
             "reabrió un corte Final ya confirmado. Cada confirmación previa "
             "sigue disponible en el histórico de cada línea -nunca se "
             "sobreescribe-, ver wk.school.colombo.grade.consolidated.line."
             "confirmed_snapshot.")
    final_reopened_date = fields.Datetime(string="Fecha de reapertura (Final)")

    line_ids = fields.One2many(
        'wk.school.colombo.grade.consolidated.line', 'consolidated_id',
        string="Resultados por estudiante")
    student_count = fields.Integer(
        string="Estudiantes", compute='_compute_student_count')

    @api.depends('line_ids')
    def _compute_student_count(self):
        for record in self:
            record.student_count = len(record.line_ids)

    @api.depends('grades_locked')
    def _compute_teacher_edit_enabled(self):
        for consolidated in self:
            consolidated.teacher_edit_enabled = not consolidated.grades_locked

    def _inverse_teacher_edit_enabled(self):
        for consolidated in self:
            consolidated.grades_locked = not consolidated.teacher_edit_enabled

    @api.depends('final_state')
    def _compute_confirmed_display(self):
        for consolidated in self:
            consolidated.confirmed_display = consolidated.final_state == 'confirmed'

    @api.depends(
        'grading_scale_id.abs_min_hours', 'grading_scale_id.abs_max_hours',
        'grading_scale_id.abs_required_average')
    def _compute_absence_rule_summary(self):
        for consolidated in self:
            scale = consolidated.grading_scale_id
            if not scale:
                consolidated.absence_rule_summary = False
                continue
            consolidated.absence_rule_summary = _(
                "Más de %(min)s y hasta %(max)s horas → aprobar con "
                "promedio > %(avg)s") % {
                    'min': scale.abs_min_hours, 'max': scale.abs_max_hours,
                    'avg': scale.abs_required_average}

    @api.depends('final_state', 'midterm_state', 'line_ids.portal_visible')
    def _compute_overall_state(self):
        for consolidated in self:
            if consolidated.final_state == 'confirmed' and any(
                    consolidated.line_ids.mapped('portal_visible')):
                consolidated.overall_state = 'published'
            elif consolidated.final_state == 'confirmed' or consolidated.midterm_state == 'confirmed':
                consolidated.overall_state = 'in_progress'
            else:
                consolidated.overall_state = 'draft'

    @api.depends('line_ids.result', 'line_ids.final_grade',
                 'line_ids.absence_hours', 'line_ids.performance_range_code',
                 'grading_scale_id.abs_min_hours')
    def _compute_stats(self):
        for consolidated in self:
            lines = consolidated.line_ids
            scored = lines.filtered(lambda l: not l.incomplete)
            total = len(lines)
            pass_lines = lines.filtered(lambda l: l.result == 'pass')
            fail_lines = lines.filtered(lambda l: l.result == 'fail')
            pending_lines = lines.filtered(lambda l: l.result == 'pending')
            consolidated.avg_final_grade = (
                sum(scored.mapped('final_grade')) / len(scored)
                if scored else 0.0)
            consolidated.pass_count = len(pass_lines)
            consolidated.fail_count = len(fail_lines)
            consolidated.pending_count = len(pending_lines)
            consolidated.pass_pct = (len(pass_lines) / total * 100.0) if total else 0.0
            consolidated.fail_pct = (len(fail_lines) / total * 100.0) if total else 0.0
            min_hours = consolidated.grading_scale_id.abs_min_hours
            consolidated.absence_alert_count = len(lines.filtered(
                lambda l: l.absence_hours > min_hours)) if min_hours else 0
            counts = {}
            for line in lines:
                if line.performance_range_code:
                    counts[line.performance_range_code] = counts.get(
                        line.performance_range_code, 0) + 1
            consolidated.performance_distribution_summary = " · ".join(
                "%s: %s" % (code, qty) for code, qty in counts.items()) or False

    def _compute_attendance_ids(self):
        Attendance = self.env['wk.student.class.attendance']
        for consolidated in self:
            consolidated.attendance_ids = Attendance.search([
                ('class_id.populate_class_id', '=', consolidated.populate_class_id.id),
            ])

    # -- Sincronización del listado de estudiantes --------------------------
    def action_refresh(self):
        """Botón "Actualizar": sincroniza matriculados y recalcula todo.

        Agrega líneas para estudiantes matriculados después de aplicar la
        estructura (requerimiento 2.9: "el usuario no debe registrar
        nuevamente las calificaciones"); nunca elimina una línea existente,
        aunque el estudiante ya no esté matriculado, para no perder su
        resultado histórico.
        """
        Line = self.env['wk.school.colombo.grade.consolidated.line']
        for consolidated in self:
            existing = consolidated.line_ids.mapped('student_subject_id')
            missing = consolidated.populate_class_id.student_ids - existing
            for student_subject in missing:
                Line.create({
                    'consolidated_id': consolidated.id,
                    'student_subject_id': student_subject.id,
                })
            consolidated.line_ids._wk_recompute_all()

    # -- Confirmación ---------------------------------------------------------
    def _check_ready_to_confirm(self, cut):
        """Valida pesos 100% y completitud antes de confirmar un corte (2.3, 2.9.4).

        La completitud se exige solo contra los componentes que pesan en
        ESE corte: confirmar Midterm no exige notas de componentes que
        solo pesan en Final (y viceversa), aunque la clase maneje 2 cortes
        (ver incomplete_midterm / incomplete en _wk_calc_components).
        """
        self.ensure_one()
        klass = self.populate_class_id
        klass._check_advanced_weight_sum()
        field = 'incomplete_midterm' if cut == 'midterm' else 'incomplete'
        incomplete = self.line_ids.filtered(lambda l: l[field])
        if incomplete:
            raise UserError(_(
                "No se puede confirmar: faltan calificaciones por "
                "registrar para %s.") % ", ".join(
                    incomplete.mapped('student_id.name')))

    def action_confirm_midterm(self):
        for consolidated in self:
            if consolidated.cuts_count != '2':
                raise UserError(_(
                    "Esta estructura no maneja Midterm por separado (1 "
                    "corte): confirme directamente el resultado Final."))
            if consolidated.midterm_state == 'confirmed':
                continue
            consolidated._check_ready_to_confirm('midterm')
            consolidated.line_ids._wk_freeze_snapshot('midterm')
            consolidated.write({
                'midterm_state': 'confirmed',
                'midterm_confirmed_by': self.env.user.id,
                'midterm_confirmed_date': fields.Datetime.now(),
            })

    def action_confirm_final(self):
        for consolidated in self:
            if consolidated.final_state == 'confirmed':
                continue
            consolidated._check_ready_to_confirm('final')
            consolidated.line_ids._wk_recompute_all(force=True)
            consolidated.line_ids._wk_freeze_snapshot('final')
            consolidated.write({
                'final_state': 'confirmed',
                'final_confirmed_by': self.env.user.id,
                'final_confirmed_date': fields.Datetime.now(),
            })

    def action_reopen_final(self):
        """Reapertura restringida a Admin, con trazabilidad (2.10, último punto).

        Requiere además que la Escala tenga activo "Permitir edición de
        calificaciones confirmadas" (2.5): sin ese check, el corte Final
        confirmado queda bloqueado para siempre, sin excepción -ni para
        Admin-.
        """
        for consolidated in self:
            if not consolidated.grading_scale_id.allow_edit_confirmed:
                raise UserError(_(
                    "Esta Escala no permite editar calificaciones "
                    "confirmadas (ver \"Permitir edición de calificaciones "
                    "confirmadas\" en Configuración adicional)."))
            if not self.env.user.has_group(
                    'wk_school_management.wk_school_management_admin_group'):
                raise UserError(_(
                    "Solo un usuario Admin puede reabrir un corte ya "
                    "confirmado."))
            consolidated.write({
                'final_state': 'draft',
                'final_reopened_by': self.env.user.id,
                'final_reopened_date': fields.Datetime.now(),
            })

    # -- Publicación en portal (masiva, sobre líneas seleccionadas) ----------
    def action_publish_all(self):
        self.mapped('line_ids').write({'portal_visible': True})

    def action_hide_all(self):
        self.mapped('line_ids').write({'portal_visible': False})

    # -- Class List: variantes para el cierre de curso (2.12) ----------------
    def _wk_print_class_list(self, variant):
        """Imprime el Class List con la variante elegida (todos/Pass/Fail).

        ``report_action(self, data={...})`` con un ``data`` no vacío hace que
        el cliente web arme la URL de descarga SIN el id del registro en la
        ruta (``getReportUrl`` en
        addons/web/static/src/webclient/actions/reports/utils.js: el id en
        la ruta -via ``active_ids``- solo se agrega cuando ``action.data``
        está vacío). El controlador recibe entonces ``docids=None`` y el
        reporte imprime un PDF vacío -sin error visible-, aunque un enlace
        directo con el id sí funcione (así se diagnosticó: un link manual a
        ``/report/pdf/.../<id>`` traía los datos bien, pero el botón real no).
        Se pasa el id también DENTRO de ``data`` para que
        ``_get_report_values`` (report/grade_consolidated_report.py) lo
        recupere igual cuando ``docids`` llega vacío.
        """
        self.ensure_one()
        return self.env.ref(
            'wk_school_colombo.report_class_list_action'
        ).report_action(self, data={'variant': variant, 'consolidated_ids': self.ids})

    def action_print_class_list_all(self):
        return self._wk_print_class_list('all')

    def action_print_class_list_pass(self):
        return self._wk_print_class_list('pass')

    def action_print_class_list_fail(self):
        return self._wk_print_class_list('fail')

    # -- Accesos directos (rediseño del Consolidado) --------------------------
    def action_view_structure(self):
        """Botón "Ver estructura": abre la Escala en una ventana aparte, de
        solo lectura -atajo directo en vez de navegar desde el campo
        Estructura de calificación-."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Estructura de calificación"),
            'res_model': 'wk.grade.scales',
            'view_mode': 'form',
            'res_id': self.grading_scale_id.id,
            'target': 'new',
            'context': {'create': False},
        }

    def action_export_csv(self):
        """Botón "Exportar": CSV con una fila por estudiante del Consolidado.

        Sin dependencia nueva (no usa report_xlsx): arma el CSV en memoria,
        lo sube como ir.attachment y devuelve la descarga directa.
        """
        self.ensure_one()
        buf = io.StringIO()
        writer = csv.writer(buf)
        header = [_("Estudiante")]
        if self.cuts_count == '2':
            header += [_("Midterm Grade"), _("Ranking Midterm")]
        header += [
            _("Final Grade"), _("Fin. Quiz Average"), _("ABS"), _("Ranking"),
            _("Rango de desempeño"), _("Pass/Fail"), _("Causa"),
            _("Estado de cursado"), _("Comentarios"), _("Visible en portal")]
        writer.writerow(header)
        result_labels = dict(self.line_ids._fields['result'].selection)
        reason_labels = dict(self.line_ids._fields['fail_reason'].selection)
        for line in self.line_ids.sorted(key=lambda l: l.ranking or 999999):
            row = [line.student_id.name]
            if self.cuts_count == '2':
                row += [line.midterm_grade, line.midterm_ranking]
            row += [
                line.final_grade, line.fin_quiz_average, line.absence_hours,
                line.ranking, line.performance_range_name or '',
                result_labels.get(line.result, ''),
                reason_labels.get(line.fail_reason, ''),
                line.course_status or '', line.comments or '',
                _("Sí") if line.portal_visible else _("No")]
            writer.writerow(row)
        content = buf.getvalue().encode('utf-8-sig')
        attachment = self.env['ir.attachment'].create({
            'name': 'Consolidado_%s.csv' % self.populate_class_id.name,
            'datas': base64.b64encode(content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'text/csv',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }


class GradeConsolidatedLine(models.Model):
    """Resultado consolidado de un estudiante en una Clase ofertada (2.9)."""

    _name = 'wk.school.colombo.grade.consolidated.line'
    _description = "Línea del Consolidado de notas"
    _order = 'ranking, student_id'

    _student_uniq = models.Constraint(
        'unique(consolidated_id, student_subject_id)',
        "Este estudiante ya tiene una línea en este Consolidado.")

    consolidated_id = fields.Many2one(
        'wk.school.colombo.grade.consolidated', string="Consolidado",
        required=True, ondelete='cascade', index=True)
    populate_class_id = fields.Many2one(
        related='consolidated_id.populate_class_id', store=True, string="Clase ofertada")
    student_subject_id = fields.Many2one(
        'wk.student.subjects', string="Matrícula de materia", required=True,
        ondelete='cascade')
    student_id = fields.Many2one(
        'student.student', related='student_subject_id.student_id', store=True)
    course_status = fields.Selection(
        related='student_subject_id.state', store=True, string="Estado de cursado")
    grade_decimals = fields.Integer(
        related='consolidated_id.grading_scale_id.grade_decimals',
        string="Decimales",
        help="Usado por el widget wk_grade_float (Resultados) para mostrar "
             "Midterm/Final Grade y Fin. Quiz Average con la cantidad de "
             "decimales configurada en la Escala (requerimiento 2.9.1: "
             "'aplicar la configuración definida para el manejo y "
             "visualización de decimales'), no siempre 2 decimales fijos.")

    midterm_grade = fields.Float(string="Midterm Grade", compute='_compute_grades', store=True)
    final_grade = fields.Float(string="Final Grade", compute='_compute_grades', store=True)
    fin_quiz_average = fields.Float(
        string="Fin. Quiz Average", compute='_compute_grades', store=True,
        help="Promedio simple e informativo de los componentes marcados "
             "\"Incluir en Fin. Quiz Average\" en la Escala. No participa "
             "directamente en el cálculo de la Final Grade: cada "
             "componente ya aporta con su propio peso.")
    incomplete = fields.Boolean(
        string="Incompleto", compute='_compute_grades', store=True,
        help="Falta al menos una calificación de un componente con peso "
             "Final mayor que 0 (con 1 corte, el único peso que existe). "
             "Bloquea la confirmación de Final y excluye la línea del "
             "ranking y del Pass/Fail mientras esté marcada.")
    incomplete_midterm = fields.Boolean(
        string="Incompleto (Midterm)", compute='_compute_grades', store=True,
        help="Falta al menos una calificación de un componente con peso "
             "Midterm mayor que 0. Solo aplica con 2 cortes; bloquea la "
             "confirmación de Midterm sin exigir que los componentes que "
             "solo pesan en Final ya estén calificados.")
    components_json = fields.Text(
        string="Detalle por componente", compute='_compute_grades', store=True,
        help="Snapshot JSON para el widget del Consolidado: nombre, peso "
             "Midterm/Final y nota de cada componente.")

    absence_hours = fields.Float(
        string="ABS / Horas de ausencia", compute='_compute_absence_hours',
        store=True, help="Acumulado automático desde Marcar Asistencia "
        "(models/class_attendance.py); no se vuelve a registrar aquí.")

    ranking = fields.Integer(string="Ranking", default=0)
    midterm_ranking = fields.Integer(string="Ranking Midterm", default=0)
    ranking_badge = fields.Char(string="Posición", compute='_compute_ranking_badge')

    result = fields.Selection([
        ('pending', 'Pendiente'), ('pass', 'Pass / Aprobado'),
        ('fail', 'Fail / Reprobado'),
    ], string="Pass/Fail", default='pending')
    fail_reason = fields.Selection([
        ('grade', 'Nota insuficiente'), ('absence', 'Regla de ausencias'),
    ], string="Causa del Fail")
    performance_range_code = fields.Char(string="Código de desempeño")
    performance_range_name = fields.Char(string="Desempeño")

    portal_visible = fields.Boolean(
        string="Visible en portal", default=False,
        help="Marcado: el estudiante ve esta calificación en su portal "
             "web. Desmarcado: sigue disponible para docentes y usuarios "
             "administrativos, pero no para el estudiante. No afecta la "
             "nota, el Pass/Fail ni el histórico (requerimiento 2.10).")
    comments = fields.Text(string="Comentarios")

    confirmed_snapshot = fields.Text(
        string="Histórico congelado (JSON)",
        help="Se escribe una sola vez, al confirmar Final (o Midterm, si "
             "aplica): estructura, componentes, ponderaciones, resultado y "
             "horas de ausencia en el momento de la consolidación. Cambios "
             "posteriores en la Escala no modifican este valor.")
    has_confirmed_snapshot = fields.Boolean(
        string="Histórico congelado", compute='_compute_has_confirmed_snapshot',
        help="Esta línea ya tiene un snapshot histórico congelado (al "
             "menos un corte confirmado para este estudiante).")

    @api.depends('confirmed_snapshot')
    def _compute_has_confirmed_snapshot(self):
        for line in self:
            line.has_confirmed_snapshot = bool(line.confirmed_snapshot)

    @api.depends('ranking')
    def _compute_ranking_badge(self):
        medals = {1: '🥇', 2: '🥈', 3: '🥉'}
        for line in self:
            if not line.ranking:
                line.ranking_badge = '-'
            else:
                icon = medals.get(line.ranking, '')
                line.ranking_badge = ('%s %s' % (icon, line.ranking)).strip()

    # -- Cálculo de notas por componente -------------------------------------
    @api.depends(
        'student_subject_id.student_assignment_ids.marks_obtained',
        'student_subject_id.student_assignment_ids.state',
        'student_subject_id.student_assignment_ids.component_id',
        'consolidated_id.populate_class_id.class_assignment_type_ids.weightage',
        'consolidated_id.populate_class_id.class_assignment_type_ids.weight_final',
        'consolidated_id.populate_class_id.class_assignment_type_ids.component_id',
        'consolidated_id.final_state')
    def _compute_grades(self):
        for line in self:
            if line.consolidated_id.final_state == 'confirmed':
                continue  # histórico ya congelado: no se recalcula (2.10)
            result = line._wk_calc_components()
            line.midterm_grade = result['midterm_grade']
            line.final_grade = result['final_grade']
            line.fin_quiz_average = result['fin_quiz_average']
            line.incomplete = result['incomplete']
            line.incomplete_midterm = result['incomplete_midterm']
            line.components_json = result['components_json']

    def _wk_calc_components(self):
        self.ensure_one()
        klass = self.consolidated_id.populate_class_id
        scale = self.consolidated_id.grading_scale_id
        # wk.class.assignment.type (Webkul) no tiene un campo propio de
        # orden: se ordena por el de su Componente de origen.
        rows = klass.class_assignment_type_ids.sorted(
            key=lambda row: row.component_id.sequence)

        by_component = {}
        for sa in self.student_subject_id.student_assignment_ids:
            if sa.component_id:
                by_component.setdefault(
                    sa.component_id.id, self.env['wk.student.assignment'])
                by_component[sa.component_id.id] |= sa

        def grade_of(component_id):
            sas = by_component.get(component_id)
            if not sas:
                return None
            scored = sas.filtered(lambda s: s.state == 'evaluate')
            if not scored:
                return None
            return sum(scored.mapped('marks_obtained')) / len(scored)

        decimals = scale.grade_decimals if scale else 2
        two_cuts = bool(scale and scale.cuts_count == '2')
        midterm_total = 0.0
        final_total = 0.0
        quiz_values = []
        incomplete_midterm = False
        incomplete_final = False
        detail = []
        for row in rows:
            component = row.component_id
            grade = grade_of(component.id) if component else None
            if row.weightage:
                if grade is None:
                    incomplete_midterm = True
                else:
                    midterm_total += grade * row.weightage / 100.0
            if two_cuts and row.weight_final:
                if grade is None:
                    incomplete_final = True
                else:
                    final_total += grade * row.weight_final / 100.0
            if component and component.in_quiz_average and grade is not None:
                quiz_values.append(grade)
            detail.append({
                'name': component.name if component else row.assignment_type_id.name,
                'weight_midterm': row.weightage,
                'weight_final': row.weight_final,
                'grade': grade,
            })

        if not two_cuts:
            final_total = midterm_total
            midterm_total = 0.0
            incomplete_final = incomplete_midterm

        return {
            'midterm_grade': round(midterm_total, decimals),
            'final_grade': round(final_total, decimals),
            'fin_quiz_average': (
                round(sum(quiz_values) / len(quiz_values), decimals)
                if quiz_values else 0.0),
            'incomplete': incomplete_final,
            'incomplete_midterm': incomplete_midterm,
            'components_json': json.dumps(detail),
        }

    # -- Horas de ausencia ----------------------------------------------------
    @api.depends('student_id', 'populate_class_id')
    def _compute_absence_hours(self):
        """Acumulado inicial; se refresca de verdad con action_refresh.

        No existe una ruta de dependencia declarativa limpia desde una
        línea del Consolidado hasta las líneas de asistencia de todas las
        sesiones de la clase (son dos relaciones independientes que solo
        se cruzan por estudiante + clase). Se calcula aquí al crear la
        línea y se refresca explícitamente con el botón "Actualizar"
        (wk.school.colombo.grade.consolidated.action_refresh) mientras el
        resultado no esté confirmado -igual que pide el requerimiento 2.11-.
        """
        Attendance = self.env['wk.student.class.attendance']
        for line in self:
            if line.consolidated_id.final_state == 'confirmed':
                continue
            if not (line.student_id and line.populate_class_id):
                line.absence_hours = 0.0
                continue
            line.absence_hours = Attendance._wk_total_absence_hours(
                line.student_id, line.populate_class_id)

    # -- Ranking, Pass/Fail y rango de desempeño ------------------------------
    def _wk_recompute_all(self, force=False):
        """Fuerza el recálculo completo (botón "Actualizar" y pre-confirmación).

        ``force=True`` ignora el bloqueo de corte confirmado -se usa justo
        antes de congelar Final, para asegurar que el histórico se escribe
        con el último dato disponible-.
        """
        lines = self.filtered(
            lambda l: force or l.consolidated_id.final_state != 'confirmed')
        if not lines:
            return
        for line in lines:
            if force or line.consolidated_id.final_state != 'confirmed':
                result = line._wk_calc_components()
                line.write({
                    'midterm_grade': result['midterm_grade'],
                    'final_grade': result['final_grade'],
                    'fin_quiz_average': result['fin_quiz_average'],
                    'incomplete': result['incomplete'],
                    'components_json': result['components_json'],
                })
            line.absence_hours = self.env[
                'wk.student.class.attendance']._wk_total_absence_hours(
                    line.student_id, line.populate_class_id)
        lines._wk_compute_ranking_and_result()

    def _wk_compute_ranking_and_result(self):
        """Ranking, Pass/Fail y rango de desempeño (2.9.1-2.9.4, 2.11).

        Es un cálculo de grupo (ranking depende de TODOS los compañeros de
        clase), por lo que se procesa por Consolidado en lugar de como un
        ``@api.depends`` por línea -más predecible que encadenar cómputos
        cruzados entre hermanos de un One2many-. Se invoca desde
        action_refresh y antes de cada confirmación.
        """
        for consolidated in self.mapped('consolidated_id'):
            scale = consolidated.grading_scale_id
            all_lines = consolidated.line_ids
            ranked = all_lines.filtered(lambda l: not l.incomplete).sorted(
                key=lambda l: l.final_grade, reverse=True)
            previous, rank = None, 0
            for idx, line in enumerate(ranked, start=1):
                if previous is None or line.final_grade != previous:
                    rank = idx
                line.ranking = rank
                previous = line.final_grade
            (all_lines - ranked).write({'ranking': 0})

            if scale and scale.cuts_count == '2':
                mid_ranked = all_lines.filtered(
                    lambda l: not l.incomplete_midterm).sorted(
                        key=lambda l: l.midterm_grade, reverse=True)
                previous, rank = None, 0
                for idx, line in enumerate(mid_ranked, start=1):
                    if previous is None or line.midterm_grade != previous:
                        rank = idx
                    line.midterm_ranking = rank
                    previous = line.midterm_grade

            for line in all_lines:
                line._wk_compute_pass_fail(scale)

    def _wk_compute_pass_fail(self, scale):
        """Pass/Fail según nota mínima y regla de ausencias (2.9.4, 2.11)."""
        self.ensure_one()
        if not scale:
            self.result = 'pending'
            return
        if self.incomplete:
            self.result = 'pending'
            self.fail_reason = False
            self._wk_compute_performance_range(scale)
            return

        hours = self.absence_hours
        grade = self.final_grade
        if scale.abs_auto_fail_above_max and hours > scale.abs_max_hours:
            result, reason = 'fail', 'absence'
        elif hours > scale.abs_min_hours:
            if grade > scale.abs_required_average:
                result, reason = 'pass', False
            else:
                result, reason = 'fail', 'absence'
        else:
            if grade >= scale.pass_grade:
                result, reason = 'pass', False
            else:
                result, reason = 'fail', 'grade'
        self.result = result
        self.fail_reason = reason
        self._wk_compute_performance_range(scale)

    def _wk_compute_performance_range(self, scale):
        self.ensure_one()
        ranges = scale.performance_range_ids.filtered(
            lambda r: r.active and r.min_grade <= self.final_grade
        ).sorted(key=lambda r: r.min_grade, reverse=True)
        if ranges:
            self.performance_range_code = ranges[0].code
            self.performance_range_name = ranges[0].name
        else:
            self.performance_range_code = False
            self.performance_range_name = False

    # -- Lectura para reportes (2.12) -----------------------------------------
    def _wk_latest_snapshot(self, cut):
        """Última confirmación congelada de un corte, o False si no existe.

        confirmed_snapshot[cut] es una LISTA (una entrada por cada vez que
        se confirmó ese corte, nunca se sobreescribe -requerimiento 2.10:
        "conservar trazabilidad... de la modificación realizada" cuando se
        reabre y se vuelve a confirmar, ver action_reopen_final). Se admite
        además el formato antiguo (un único dict por corte, de antes de este
        cambio) para no perder el histórico ya guardado en producción.
        """
        self.ensure_one()
        entry = json.loads(self.confirmed_snapshot or '{}').get(cut)
        if not entry:
            return False
        return entry[-1] if isinstance(entry, list) else entry

    def _wk_report_components(self, cut):
        """Componentes a imprimir para un corte, respetando el histórico.

        Si el corte ya está confirmado, lee el detalle congelado en
        confirmed_snapshot (la estructura/ponderaciones del momento de la
        consolidación); si no, usa el cálculo en vivo (components_json).
        Solo devuelve los componentes con peso > 0 en ese corte -los que
        no participan no deben imprimirse-.
        """
        self.ensure_one()
        snapshot = self._wk_latest_snapshot(cut)
        source = snapshot['components'] if snapshot else json.loads(
            self.components_json or '[]')
        scale = self.consolidated_id.grading_scale_id
        one_cut = not (scale and scale.cuts_count == '2')
        key = 'weight_midterm' if (cut == 'midterm' or one_cut) else 'weight_final'
        return [c for c in source if (c.get(key) or 0) > 0]

    def _wk_report_grade(self, cut):
        self.ensure_one()
        field = 'midterm_grade' if cut == 'midterm' else 'final_grade'
        snapshot = self._wk_latest_snapshot(cut)
        if snapshot:
            return snapshot.get(field, 0.0)
        return self[field]

    def write(self, vals):
        """Restringe quién administra la visibilidad en portal (2.10).

        "Los usuarios administrativos autorizados deberán disponer desde el
        consolidado de las acciones necesarias para... Publicar/Ocultar
        notas en portal": sin este chequeo, un docente con acceso de
        escritura a sus propias clases (ver ir_rule.xml,
        grade_consolidated_line_teacher_rule) podría publicar u ocultar
        calificaciones él mismo con solo marcar el check en la vista -la
        vista ya lo oculta con ``groups=``, esto cubre además cualquier
        escritura por API/automatización-.
        """
        if 'portal_visible' in vals and not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "Solo un usuario Officer/Admin puede publicar u ocultar "
                "calificaciones en el portal del estudiante."))
        return super().write(vals)

    # -- Publicación en portal (individual o sobre la selección) -------------
    def action_publish_selected(self):
        self.write({'portal_visible': True})

    def action_hide_selected(self):
        self.write({'portal_visible': False})

    # -- Histórico congelado ---------------------------------------------------
    def _wk_freeze_snapshot(self, cut):
        """Agrega una entrada al histórico congelado, al confirmar (2.10).

        confirmed_snapshot[cut] es una LISTA, nunca se sobreescribe: si un
        corte se reabre (action_reopen_final) y se vuelve a confirmar, la
        confirmación anterior sigue disponible -requerimiento 2.10: "Las
        modificaciones realizadas después de la confirmación deberán...
        conservar trazabilidad del usuario, fecha y modificación
        realizada"-. ``confirmed_by``/``confirmed_date`` quedan en cada
        entrada porque los campos de cabecera (final_confirmed_by/date) se
        sobreescriben en cada nueva confirmación.
        """
        for line in self:
            scale = line.consolidated_id.grading_scale_id
            snapshot = {
                'cut': cut,
                'confirmed_by': self.env.user.display_name,
                'confirmed_date': fields.Datetime.now().isoformat(),
                'student': line.student_id.display_name,
                'populate_class': line.populate_class_id.display_name,
                'program_type': scale.program_type_id.name if scale else False,
                'modality': scale.modality if scale else False,
                'academic_year': line.consolidated_id.academic_year_id.display_name,
                'grading_scale': scale.name if scale else False,
                'components': json.loads(line.components_json or '[]'),
                'midterm_grade': line.midterm_grade,
                'final_grade': line.final_grade,
                'result': line.result,
                'fail_reason': line.fail_reason,
                'absence_hours': line.absence_hours,
                'performance_range': line.performance_range_name,
                'ranking': line.ranking,
            }
            previous = json.loads(line.confirmed_snapshot or '{}')
            history = previous.get(cut) or []
            if isinstance(history, dict):
                history = [history]  # formato antiguo (una sola entrada)
            history.append(snapshot)
            previous[cut] = history
            line.confirmed_snapshot = json.dumps(previous)


class StudentSubjectConsolidated(models.Model):
    """Expone los resultados de estructura avanzada de una Matrícula de
    materia, para que student.enrollment._compute_academic_result (subtarea
    6, models/student_enrollment.py) pueda usarlos sin que esta subtarea
    tenga que tocar el mecanismo estándar scale_line_id.passes -que una
    estructura avanzada no utiliza-.
    """

    _inherit = 'wk.student.subjects'

    consolidated_line_ids = fields.One2many(
        'wk.school.colombo.grade.consolidated.line', 'student_subject_id',
        string="Resultados en estructura avanzada")
