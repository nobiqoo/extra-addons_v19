# -*- coding: utf-8 -*-
"""Reportes académicos del Consolidado de notas (subtarea 8, 2.12).

Los tres reportes (Midterm, Final y Class List) leen siempre la
información ya consolidada -snapshot congelado si el corte está
confirmado, cálculo en vivo si todavía no- sin requerir que el usuario
calcule nada manualmente. Midterm solo aplica a estructuras de 2 cortes.
"""
from odoo import models, _
from odoo.exceptions import UserError


class GradeConsolidatedMidtermReport(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_grade_midterm_document'
    _description = "Reporte Midterm del Consolidado de notas"

    def _get_report_values(self, docids, data=None):
        consolidated = self.env['wk.school.colombo.grade.consolidated'].browse(docids)
        if consolidated.filtered(lambda c: c.cuts_count != '2'):
            raise UserError(_(
                "El Reporte Midterm solo aplica a estructuras de 2 cortes."))
        return {
            'doc_ids': docids,
            'doc_model': 'wk.school.colombo.grade.consolidated',
            'docs': consolidated,
            'wk_cut': 'midterm',
        }


class GradeConsolidatedFinalReport(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_grade_final_document'
    _description = "Reporte Final del Consolidado de notas"

    def _get_report_values(self, docids, data=None):
        consolidated = self.env['wk.school.colombo.grade.consolidated'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'wk.school.colombo.grade.consolidated',
            'docs': consolidated,
            'wk_cut': 'final',
        }


class PerformanceDistributionReport(models.AbstractModel):
    """Reporte de Distribución por Desempeño (2.5).

    Agrupa a los estudiantes de la clase por rango de desempeño (sobre la
    Final Grade ya consolidada), en el mismo orden de los rangos activos de
    la Escala (de mayor a menor Nota mínima). Los estudiantes sin rango
    (resultado pendiente, línea incompleta) quedan en un grupo aparte "Sin
    clasificar" al final.
    """
    _name = 'report.wk_school_colombo.report_performance_distribution'
    _description = "Reporte de Distribución por Desempeño"

    def _get_report_values(self, docids, data=None):
        consolidated = self.env['wk.school.colombo.grade.consolidated'].browse(docids)
        groups = []
        for doc in consolidated:
            lines = doc.line_ids
            total = len(lines)
            ranges = doc.grading_scale_id.performance_range_ids.filtered(
                'active').sorted(key=lambda r: r.min_grade, reverse=True)
            doc_groups = []
            classified = self.env['wk.school.colombo.grade.consolidated.line']
            for rng in ranges:
                group_lines = lines.filtered(
                    lambda l, code=rng.code: l.performance_range_code == code)
                classified |= group_lines
                doc_groups.append({
                    'code': rng.code,
                    'name': rng.name,
                    'count': len(group_lines),
                    'pct': (len(group_lines) / total * 100.0) if total else 0.0,
                    'lines': group_lines.sorted(key=lambda l: l.final_grade, reverse=True),
                })
            unclassified = lines - classified
            if unclassified:
                doc_groups.append({
                    'code': False,
                    'name': _("Sin clasificar"),
                    'count': len(unclassified),
                    'pct': (len(unclassified) / total * 100.0) if total else 0.0,
                    'lines': unclassified.sorted(key=lambda l: l.student_id.name or ''),
                })
            groups.append((doc.id, doc_groups))
        return {
            'doc_ids': docids,
            'doc_model': 'wk.school.colombo.grade.consolidated',
            'docs': consolidated,
            'wk_groups': dict(groups),
        }


class ClassListReport(models.AbstractModel):
    _name = 'report.wk_school_colombo.report_class_list_document'
    _description = "Class List"

    def _get_report_values(self, docids, data=None):
        data = data or {}
        # Los botones "Class List (todos/Pass/Fail)" llaman a report_action
        # con un `data` no vacío (la variante), lo que hace que el cliente
        # web omita el id en la URL de descarga (ver _wk_print_class_list en
        # models/grade_consolidated.py) y `docids` llegue vacío: se usa el
        # id que se guardó dentro de `data` como respaldo.
        docids = docids or data.get('consolidated_ids')
        consolidated = self.env['wk.school.colombo.grade.consolidated'].browse(docids)
        variant = data.get('variant', 'all')
        lines = consolidated.line_ids
        if variant == 'pass':
            lines = lines.filtered(lambda l: l.result == 'pass')
        elif variant == 'fail':
            lines = lines.filtered(lambda l: l.result == 'fail')
        return {
            'doc_ids': docids,
            'doc_model': 'wk.school.colombo.grade.consolidated',
            'docs': consolidated,
            'wk_lines': lines.sorted(key=lambda l: l.student_id.name or ''),
            'wk_variant': variant,
        }
