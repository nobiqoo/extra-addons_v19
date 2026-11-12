# -*- coding: utf-8 -*-
"""Wizard "Reportes de Análisis Académico" (Ajuste y ampliación de Reportes
Académicos): nueva opción en Informes que genera en Excel el Reporte de
Distribución por Desempeño y el Reporte de Retención/Promoción/Pérdida/
Deserción, a partir de los Consolidados de notas (wk.school.colombo.grade.
consolidated) del Programa/Periodo/Sede seleccionados -sin recalcular
Final Grade, Pass/Fail ni rango de desempeño, ya calculados por el
Consolidado-.

El filtro "Programa" vive en la Escala de calificación aplicada a cada
Clase ofertada (grading_scale_id.program_type_id, ver models/
grade_consolidated.py), por lo que el alcance real de este wizard son los
Consolidados cuyo program_type_id/academic_year_id (y, si se indica,
populate_class_id.sede_id) coincidan: eso ya incluye automáticamente todos
los niveles, módulos, clases ofertadas y horarios del Programa, tal como
pide el requerimiento.
"""
import base64
import io

import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import UserError

REPORT_TYPE_SELECTION = [
    ('distribution', "Reporte de Distribución por Desempeño"),
    ('retention', "Reporte de Retención, Promoción, Pérdida y Deserción"),
]


class WkSchoolColomboAcademicAnalysisWizard(models.TransientModel):
    _name = 'wk.school.colombo.academic.analysis.wizard'
    _description = "Reportes de Análisis Académico"

    report_type = fields.Selection(
        REPORT_TYPE_SELECTION, string="Tipo de reporte",
        default='distribution', required=True)
    academic_year_id = fields.Many2one(
        'wk.academic.year', string="Periodo académico", required=True)
    program_type_id = fields.Many2one(
        'wk.school.colombo.program.type', string="Programa", required=True,
        help="Agrupador principal: incluye automáticamente todos los "
             "niveles, módulos, clases ofertadas y horarios asociados al "
             "programa dentro del periodo seleccionado.")
    sede_id = fields.Many2one(
        'wk.school.colombo.sede', string="Sede",
        help="Opcional: sin seleccionar, el reporte incluye todas las "
             "sedes.")

    def _wk_get_consolidated(self):
        self.ensure_one()
        domain = [
            ('program_type_id', '=', self.program_type_id.id),
            ('academic_year_id', '=', self.academic_year_id.id),
        ]
        if self.sede_id:
            domain.append(('populate_class_id.sede_id', '=', self.sede_id.id))
        consolidated = self.env['wk.school.colombo.grade.consolidated'].search(domain)
        if not consolidated:
            raise UserError(_(
                "No se encontraron Clases ofertadas con Consolidado de "
                "notas para el Programa, Periodo académico y Sede "
                "seleccionados."))
        return consolidated

    def action_generate_excel(self):
        self.ensure_one()
        consolidated = self._wk_get_consolidated()
        if self.report_type == 'distribution':
            return self._wk_generate_distribution_excel(consolidated)
        return self._wk_generate_retention_excel(consolidated)

    # -- Helpers comunes --------------------------------------------------
    def _wk_now_label(self):
        return fields.Datetime.context_timestamp(
            self, fields.Datetime.now()).strftime('%Y-%m-%d %H:%M:%S')

    def _wk_write_meta_block(self, sheet, bold, title):
        sheet.write(0, 0, title, bold)
        sheet.write(1, 0, "PROGRAMA:", bold)
        sheet.write(1, 1, self.program_type_id.name or '')
        sheet.write(2, 0, "SEDE:", bold)
        sheet.write(2, 1, self.sede_id.name or "Todas")
        sheet.write(3, 0, "PERIODO ACADÉMICO:", bold)
        sheet.write(3, 1, self.academic_year_id.display_name or '')
        sheet.write(4, 0, "GENERADO:", bold)
        sheet.write(4, 1, self._wk_now_label())

    def _wk_attachment_download(self, filename, content):
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': ('application/vnd.openxmlformats-officedocument'
                         '.spreadsheetml.sheet'),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    # -- Reporte de Distribución por Desempeño -----------------------------
    def _wk_generate_distribution_excel(self, consolidated):
        lines = consolidated.mapped('line_ids')
        ranges = consolidated.mapped('grading_scale_id.performance_range_ids').filtered('active')
        by_code = {}
        for rng in ranges.sorted(key=lambda r: (r.sequence, -r.min_grade)):
            by_code.setdefault(rng.code, rng)
        ordered_ranges = sorted(by_code.values(), key=lambda r: r.min_grade, reverse=True)

        classified = lines.filtered(lambda l: l.performance_range_code)
        total = len(classified)
        rows = []
        for rng in ordered_ranges:
            count = len(classified.filtered(
                lambda l, code=rng.code: l.performance_range_code == code))
            rows.append({
                'code': rng.code,
                'name': rng.name,
                'range': '%.1f - %.1f' % (rng.min_grade, rng.max_grade),
                'count': count,
                'pct': (count / total) if total else 0.0,
            })

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Distribución')
        bold = workbook.add_format({'bold': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 12})
        pct_format = workbook.add_format({'num_format': '0.0%'})

        self._wk_write_meta_block(sheet, title_format, "REPORTE DE DISTRIBUCIÓN POR DESEMPEÑO")

        header_row = 6
        headers = [
            "Código", "Desempeño", "Rango de calificación",
            "No. de estudiantes", "Porcentaje de estudiantes",
        ]
        for col, label in enumerate(headers):
            sheet.write(header_row, col, label, bold)

        row_idx = header_row + 1
        for row in rows:
            sheet.write(row_idx, 0, row['code'])
            sheet.write(row_idx, 1, row['name'])
            sheet.write(row_idx, 2, row['range'])
            sheet.write(row_idx, 3, row['count'])
            sheet.write(row_idx, 4, row['pct'], pct_format)
            row_idx += 1

        sheet.write(row_idx, 0, "TOTAL No. DE ESTUDIANTES", bold)
        sheet.write(row_idx, 3, total, bold)
        sheet.write(row_idx, 4, 1.0 if total else 0.0, pct_format)

        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 24)
        sheet.set_column(2, 2, 22)
        sheet.set_column(3, 4, 20)
        workbook.close()

        return self._wk_attachment_download(
            'Reporte_Distribucion_Desempeno_%s.xlsx' % (self.academic_year_id.name or ''),
            output.getvalue())

    # -- Reporte de Retención, Promoción, Pérdida y Deserción --------------
    def _wk_generate_retention_excel(self, consolidated):
        Attendance = self.env['wk.student.class.attendance']
        tag = self.env.ref(
            'wk_school_colombo.attendance_tag_desercion', raise_if_not_found=False)

        rows = []
        totals = dict(total=0, retained=0, promoted=0, failed=0, deserted=0)
        ordered = consolidated.sorted(
            key=lambda c: (c.grade_id.name or '', c.populate_class_id.weekly_schedule_summary or ''))
        for cons in ordered:
            klass = cons.populate_class_id
            lines = cons.line_ids
            deserted_student_ids = set()
            if tag:
                attendances = Attendance.search([
                    ('class_id.populate_class_id', '=', klass.id),
                    ('attendance_tag_ids', '=', tag.id),
                ])
                deserted_student_ids = set(attendances.mapped('student_id').ids)

            total = len(lines)
            deserted_lines = lines.filtered(
                lambda l: l.student_id.id in deserted_student_ids)
            retained_lines = lines - deserted_lines
            deserted = len(deserted_lines)
            retained = len(retained_lines)
            promoted = len(retained_lines.filtered(lambda l: l.result == 'pass'))
            failed = len(retained_lines.filtered(lambda l: l.result == 'fail'))

            rows.append({
                'period': self.academic_year_id.display_name or '',
                'grade': cons.grade_id.name or '',
                'schedule': klass.weekly_schedule_summary or '',
                'total': total, 'retained': retained, 'promoted': promoted,
                'failed': failed, 'deserted': deserted,
            })
            totals['total'] += total
            totals['retained'] += retained
            totals['promoted'] += promoted
            totals['failed'] += failed
            totals['deserted'] += deserted

        pct_retention = (totals['retained'] / totals['total']) if totals['total'] else 0.0
        pct_promotion = (totals['promoted'] / totals['retained']) if totals['retained'] else 0.0
        pct_failure = (totals['failed'] / totals['retained']) if totals['retained'] else 0.0
        pct_desertion = (totals['deserted'] / totals['total']) if totals['total'] else 0.0

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Retención')
        bold = workbook.add_format({'bold': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 12})
        pct_format = workbook.add_format({'num_format': '0.0%'})

        self._wk_write_meta_block(
            sheet, title_format,
            "ESTUDIANTES RETENIDOS, PROMOVIDOS, PERDIDOS Y DESERTADOS")

        header_row = 6
        headers = [
            "Periodo", "Nivel", "Horario", "Total estudiantes",
            "Estudiantes retenidos", "Promovidos", "Perdidos",
            "Estudiantes desertados",
        ]
        for col, label in enumerate(headers):
            sheet.write(header_row, col, label, bold)

        row_idx = header_row + 1
        for row in rows:
            sheet.write(row_idx, 0, row['period'])
            sheet.write(row_idx, 1, row['grade'])
            sheet.write(row_idx, 2, row['schedule'])
            sheet.write(row_idx, 3, row['total'])
            sheet.write(row_idx, 4, row['retained'])
            sheet.write(row_idx, 5, row['promoted'])
            sheet.write(row_idx, 6, row['failed'])
            sheet.write(row_idx, 7, row['deserted'])
            row_idx += 1

        sheet.write(row_idx, 0, "TOTAL", bold)
        sheet.write(row_idx, 3, totals['total'], bold)
        sheet.write(row_idx, 4, totals['retained'], bold)
        sheet.write(row_idx, 5, totals['promoted'], bold)
        sheet.write(row_idx, 6, totals['failed'], bold)
        sheet.write(row_idx, 7, totals['deserted'], bold)

        row_idx += 2
        for label, value in (
                ("% Retención", pct_retention), ("% Promoción", pct_promotion),
                ("% Pérdida", pct_failure), ("% Deserción", pct_desertion)):
            sheet.write(row_idx, 0, label, bold)
            sheet.write(row_idx, 1, value, pct_format)
            row_idx += 1

        sheet.set_column(0, 2, 20)
        sheet.set_column(3, 7, 18)
        workbook.close()

        return self._wk_attachment_download(
            ('Reporte_Retencion_Promocion_Perdida_Desercion_%s.xlsx'
             % (self.academic_year_id.name or '')),
            output.getvalue())
