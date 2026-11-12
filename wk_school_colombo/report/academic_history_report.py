# -*- coding: utf-8 -*-
"""Reporte PDF del Historial académico del estudiante (tarea 12438): agrupa
por Programa la misma trayectoria consolidada que usa la pantalla (ver
models/academic_history.py), con el detalle de calificaciones de la clase
más reciente y las observaciones generales del estudiante al final -mismo
"formato solicitado" de la tarea-. No reemplaza ni toca el reporte/portal
de transcripción estándar de Webkul (student_transcript_print), que sigue
funcionando igual para quien lo use.
"""
from odoo import models


class AcademicHistoryReport(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_academic_history_document'
    _description = "Historial académico del estudiante"

    def _get_report_values(self, docids, data=None):
        students = self.env['student.student'].browse(docids)
        students._wk_check_academic_history_access()
        wk_data = {}
        for student in students:
            rows = student._wk_academic_history_rows()
            programs = {}
            for row in rows:
                programs.setdefault(row['program'] or '-', []).append(row)
            wk_data[student.id] = {
                'header': student._wk_academic_history_header(rows),
                'programs': programs,
                'latest': rows[0] if rows else False,
                'general_observations': student._wk_academic_history_general_observations(),
            }
        return {
            'doc_ids': docids,
            'doc_model': 'student.student',
            'docs': students,
            'wk_data': wk_data,
        }
