# -*- coding: utf-8 -*-
"""Ajuste y ampliación del Histórico Académico del Estudiante (tarea 12438).

Amplía la pantalla existente "Gestión Educativa → Informes → Historial
académico" (OWL de wk_school_management, ver static/src/js/
transcript_patch.js) para mostrar, de forma consolidada, TODA la trayectoria
académica del estudiante (todos los programas, periodos, niveles/módulos y
clases cursadas), leyendo siempre la información ya consolidada -Consolidado
de notas (subtarea 8), Resultado académico y Promoción/Finalización
(subtarea 6), Observaciones- sin recalcular ni duplicar nada.

Esta es la fuente ÚNICA de datos que usan tanto la pantalla (vía
wk_fetch_academic_history) como el reporte PDF nuevo
(report/academic_history_report.py): un solo lugar para no tener dos lógicas
distintas armando la misma información.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .student_enrollment import ACADEMIC_RESULT_SELECTION
from .student_status_log import ACADEMIC_STATUS_SELECTION


class StudentStudentAcademicHistory(models.Model):
    _inherit = 'student.student'

    @api.model
    def wk_fetch_academic_history(self, student_id):
        """Punto de entrada único desde la pantalla OWL (JS) parchada.

        Devuelve el encabezado del estudiante y la trayectoria completa, ya
        lista para pintar (sin que el frontend tenga que volver a pedir el
        detalle de cada fila: cada fila ya trae su propio detalle de
        calificaciones embebido, si la clase tiene Consolidado de notas).
        """
        self._wk_check_academic_history_access()
        student = self.browse(student_id)
        if not student.exists():
            raise UserError(_("Estudiante no encontrado."))
        rows = student._wk_academic_history_rows()
        return {
            'header': student._wk_academic_history_header(rows),
            'rows': rows,
        }

    def _wk_check_academic_history_access(self):
        """Requerimiento 2.11 (permisos): consulta exclusiva de Officer/Admin.

        La vista ya restringe el menú "Historial académico" a ese grupo
        (wk_school_management.student_transcript_menu), pero se repite aquí
        -cinturón y tirantes- por si el método se invoca por API o por otra
        vía que no pase por el menú.
        """
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "No tiene permisos para consultar el Historial académico."))

    def _wk_academic_history_header(self, rows):
        self.ensure_one()
        programs = sorted({row['program'] for row in rows if row.get('program')})
        return {
            'student_id': self.id,
            'name': self.name,
            'document': self.partner_id.vat or '',
            'birth_date': fields.Date.to_string(self.dob) if self.dob else '',
            'email': self.email or '',
            'phone': self.mobile or '',
            'programs': ', '.join(programs),
            'status': dict(ACADEMIC_STATUS_SELECTION).get(self.academic_status) or '',
            'generated_date': fields.Date.to_string(fields.Date.context_today(self)),
            'generated_by': self.env.user.display_name,
        }

    def _wk_academic_history_rows(self):
        """Una fila por Clase ofertada cursada (wk.student.subjects), a
        través de TODAS las Inscripciones del estudiante -no solo una
        Programación académica-, más reciente primero.

        No hay FK directa de wk.student.subjects hacia su Clase ofertada
        (solo el M2M inverso wk.school.class.student_ids, ver skill
        wk-school-colombo "Relación estudiante ↔ clase"): se resuelve con
        una sola búsqueda por todas las Materias del estudiante en vez de
        una búsqueda por fila.
        """
        self.ensure_one()
        Klass = self.env['wk.school.class']
        ContinuityLog = self.env['wk.school.colombo.enrollment.continuity.log']
        Observation = self.env['wk.school.colombo.observation']

        enrollments = self.enrollment_ids
        subjects = enrollments.mapped('student_subject_ids')
        subject_to_class = {}
        if subjects:
            subject_id_set = set(subjects.ids)
            classes = Klass.search([('student_ids', 'in', subjects.ids)])
            for klass in classes:
                for subject in klass.student_ids:
                    if subject.id in subject_id_set:
                        subject_to_class[subject.id] = klass

        action_type_labels = dict(ContinuityLog._fields['action_type'].selection)
        rows = []
        for enrollment in enrollments:
            continuity_log = ContinuityLog.search(
                [('origin_enrollment_id', '=', enrollment.id)],
                order='create_date desc', limit=1)
            for subject in enrollment.student_subject_ids:
                klass = subject_to_class.get(subject.id)
                line = subject.consolidated_line_ids[:1]
                consolidated = line.consolidated_id if line else False

                observations = Observation.search([
                    ('enrollment_id', '=', enrollment.id),
                    ('school_class_id', '=', klass.id if klass else False),
                ])

                date_end = klass.end_date if klass else False
                action_date = ''
                action_label = ''
                if continuity_log:
                    action_label = action_type_labels.get(continuity_log.action_type, '')
                    action_date = fields.Datetime.to_string(continuity_log.create_date)
                elif enrollment.continuity_action == 'finalized' and enrollment.finalization_date:
                    action_label = _("Finalizado")
                    action_date = fields.Date.to_string(enrollment.finalization_date)

                rows.append({
                    'subject_id': subject.id,
                    'enrollment_id': enrollment.id,
                    'program': (
                        (consolidated.program_type_id.name if consolidated else False)
                        or self.program_type_id.name or ''),
                    'period': (
                        (klass.academic_year_id.display_name if klass else False)
                        or enrollment.academic_year_id.display_name or ''),
                    'grade_module': (
                        "%s / %s" % (klass.grade_id.name or '', klass.subject_id.name or '')
                        if klass else (enrollment.grade_id.name or '')),
                    'class_name': klass.display_name if klass else (subject.subject_id.name or ''),
                    'enrollment_name': enrollment.name or '',
                    'date_start': fields.Date.to_string(klass.start_date) if klass and klass.start_date else '',
                    'date_end': fields.Date.to_string(date_end) if date_end else '',
                    'academic_result': dict(ACADEMIC_RESULT_SELECTION).get(
                        enrollment.academic_result, ''),
                    'final_grade': line.final_grade if line else None,
                    'pass_fail': (
                        dict(line._fields['result'].selection).get(line.result, '')
                        if line else ''),
                    'absence_hours': line.absence_hours if line else 0.0,
                    'performance_range': line.performance_range_name if line else '',
                    'academic_status': dict(ACADEMIC_STATUS_SELECTION).get(
                        self.academic_status, ''),
                    'action_taken': action_label,
                    'action_date': action_date,
                    'observations': ' | '.join(observations.mapped('comment')),
                    'detail': self._wk_academic_history_detail(line) if line else False,
                    '_sort_key': date_end or (
                        enrollment.create_date.date() if enrollment.create_date else False),
                })

        rows.sort(key=lambda r: r['_sort_key'] or fields.Date.from_string('1900-01-01'), reverse=True)
        for row in rows:
            row.pop('_sort_key', None)
        return rows

    def _wk_academic_history_general_observations(self):
        """Observaciones "generales del estudiante" (2.8) para el PDF: las
        que no quedaron ligadas a una Clase concreta de la trayectoria
        (``school_class_id`` vacío) -las que sí tienen Clase ya se muestran
        por fila, ver _wk_academic_history_rows-.
        """
        self.ensure_one()
        observations = self.env['wk.school.colombo.observation'].search([
            ('enrollment_id', 'in', self.enrollment_ids.ids),
            ('school_class_id', '=', False),
        ])
        return '\n'.join(observations.mapped('comment'))

    def _wk_academic_history_detail(self, line):
        """Detalle de calificaciones de UNA Clase cursada (2.3): componentes
        de ambos cortes cuando la Escala maneja Midterm y Final, o solo del
        corte único cuando aplica -nunca se recalcula nada, se reutilizan
        los mismos métodos de lectura del Consolidado (_wk_report_components/
        _wk_report_grade) que ya usan los reportes de la tarea 12436-.
        """
        line.ensure_one()
        consolidated = line.consolidated_id
        detail = {
            'cuts_count': consolidated.cuts_count,
            'final_components': [{
                'name': c['name'],
                'weight': c['weight_final'] if c['weight_final'] else c['weight_midterm'],
                'grade': c['grade'],
            } for c in line._wk_report_components('final')],
            'final_grade': line._wk_report_grade('final'),
            'ranking': line.ranking,
            'absence_hours': line.absence_hours,
            'result': dict(line._fields['result'].selection).get(line.result, ''),
            'performance_range': line.performance_range_name or '',
            'comments': line.comments or '',
            'observation': line.observation or '',
        }
        if consolidated.cuts_count == '2':
            detail['midterm_components'] = [{
                'name': c['name'],
                'weight': c['weight_midterm'],
                'grade': c['grade'],
            } for c in line._wk_report_components('midterm')]
            detail['midterm_grade'] = line._wk_report_grade('midterm')
            detail['midterm_ranking'] = line.midterm_ranking
        return detail
