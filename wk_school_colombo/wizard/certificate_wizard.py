# -*- coding: utf-8 -*-
"""Wizard "Generar Certificados Académicos" (tarea 12451).

Menú único Gestión Educativa > Informes > Certificados. El usuario NUNCA
selecciona manualmente el tipo de certificado ni la plantilla (2.2, 2.17):
se infieren de la combinación Programa + Tipo de población + Nivel + Sede
(regular) o Programa "Avanzado" + Clase ofertada (ver
models/program_type.py::is_advanced_program).
"""
import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.certificate import GENERATION_MODE_SELECTION
from ..models.student_enrollment import POPULATION_TYPE_SELECTION

LIBRO_FOLIO_MODE_SELECTION = [
    ('comun', 'Común para todos'),
    ('individual', 'Individual por estudiante'),
]


class WkSchoolColomboCertificateWizard(models.TransientModel):
    _name = 'wk.school.colombo.certificate.wizard'
    _description = 'Generar Certificados Académicos'

    program_type_id = fields.Many2one(
        'wk.school.colombo.program.type', string="Programa / Módulo",
        required=True)
    is_advanced = fields.Boolean(
        related='program_type_id.is_advanced_program', readonly=True)

    # -- Modo regular (Inglés Básico/Intermedio) ---------------------------
    population_type = fields.Selection(
        POPULATION_TYPE_SELECTION, string="Tipo de población")
    grade_id = fields.Many2one('wk.school.grade', string="Nivel")

    # -- Modo Avanzado ------------------------------------------------------
    populate_class_id = fields.Many2one(
        'wk.school.class', string="Clase ofertada",
        domain="[('program_type_id', '=', program_type_id), "
               "('sede_id', '=', sede_id)]",
        help="El nombre del curso (Título) y el Docente de esta Clase "
             "ofertada se usan tal cual en el certificado.")

    sede_id = fields.Many2one(
        'wk.school.colombo.sede', string="Sede", required=True)

    generation_mode = fields.Selection([
        ('individual', 'Individual'), ('grupal', 'Grupal'),
    ], string="Modalidad de generación", required=True, default='individual')

    eligible_student_ids = fields.Many2many(
        'student.student', string="Estudiantes elegibles",
        compute='_compute_eligible_student_ids')
    student_ids = fields.Many2many(
        'student.student', string="Estudiante(s)",
        domain="[('id', 'in', eligible_student_ids)]")

    intensidad_horaria = fields.Integer(
        string="Intensidad horaria (horas)", required=True)
    date_from = fields.Date(string="Fecha de inicio")
    date_to = fields.Date(string="Fecha de finalización")
    fecha_expedicion = fields.Date(
        string="Fecha de expedición", required=True,
        default=lambda self: fields.Date.context_today(self))
    lugar_expedicion = fields.Char(string="Lugar de expedición", required=True)

    libro_folio_mode = fields.Selection(
        LIBRO_FOLIO_MODE_SELECTION, string="Libro/Folio/Consecutivo",
        default='comun')
    libro = fields.Char(string="Libro")
    folio = fields.Char(string="Folio")
    consecutivo = fields.Char(string="Consecutivo")
    line_ids = fields.One2many(
        'wk.school.colombo.certificate.wizard.line', 'wizard_id',
        string="Libro/Folio/Consecutivo por estudiante")

    @api.depends('program_type_id', 'population_type', 'grade_id', 'sede_id',
                 'is_advanced', 'populate_class_id')
    def _compute_eligible_student_ids(self):
        for wizard in self:
            if wizard.is_advanced:
                wizard.eligible_student_ids = (
                    wizard.populate_class_id.enrolled_student_ids)
                continue
            if not (wizard.program_type_id and wizard.population_type
                    and wizard.grade_id and wizard.sede_id):
                wizard.eligible_student_ids = False
                continue
            # student.enrollment no tiene program_type_id propio -ese campo
            # vive en wk.application.form y se copia a student.student,
            # nunca a la Inscripción (ver wizard/enroll_wizard.py::
            # _wk_copy_application_fields_to_student)-, así que el Programa
            # se filtra a través del Estudiante.
            enrollments = self.env['student.enrollment'].search([
                ('student_id.program_type_id', '=', wizard.program_type_id.id),
                ('population_type', '=', wizard.population_type),
                ('grade_id', '=', wizard.grade_id.id),
                ('sede_id', '=', wizard.sede_id.id),
                ('academic_result', '=', 'approved'),
            ])
            wizard.eligible_student_ids = enrollments.student_id

    @api.onchange('sede_id')
    def _onchange_sede_suggest_lugar_expedicion(self):
        if not self.sede_id or self.lugar_expedicion:
            return
        config = self.env['wk.school.colombo.certificate.config'].search(
            [('sede_id', '=', self.sede_id.id)], limit=1)
        if config:
            self.lugar_expedicion = config.lugar_expedicion

    @api.onchange('student_ids', 'generation_mode', 'libro_folio_mode')
    def _onchange_sync_lines(self):
        if self.generation_mode != 'grupal' or self.libro_folio_mode != 'individual':
            self.line_ids = [(5, 0, 0)]
            return
        existing = {line.student_id.id: line for line in self.line_ids}
        new_lines = []
        for student in self.student_ids:
            line = existing.get(student.id)
            if line:
                new_lines.append((0, 0, {
                    'student_id': student.id,
                    'libro': line.libro,
                    'folio': line.folio,
                    'consecutivo': line.consecutivo,
                }))
            else:
                new_lines.append((0, 0, {'student_id': student.id}))
        self.line_ids = [(5, 0, 0)] + new_lines

    def _wk_check_permissions(self):
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "Solo un usuario autorizado (Officer o Admin) puede generar "
                "Certificados académicos."))

    def _wk_get_libro_folio(self, student):
        self.ensure_one()
        if self.libro_folio_mode == 'individual':
            line = self.line_ids.filtered(lambda l: l.student_id == student)[:1]
            return line.libro, line.folio, line.consecutivo
        return self.libro, self.folio, self.consecutivo

    def action_generate_certificate(self):
        self.ensure_one()
        self._wk_check_permissions()

        if self.generation_mode == 'individual' and len(self.student_ids) != 1:
            raise UserError(_(
                "La modalidad Individual requiere seleccionar exactamente "
                "un estudiante."))
        if not self.student_ids:
            raise UserError(_("Seleccione al menos un estudiante."))

        if self.is_advanced:
            if not self.populate_class_id:
                raise UserError(_(
                    "Seleccione la Clase ofertada del Programa Avanzado."))
        else:
            if not (self.population_type and self.grade_id):
                raise UserError(_(
                    "Seleccione el Tipo de población y el Nivel."))
            missing_libro_folio = []
            for student in self.student_ids:
                libro, folio, consecutivo = self._wk_get_libro_folio(student)
                if not (libro and folio and consecutivo):
                    missing_libro_folio.append(student.name)
            if missing_libro_folio:
                raise UserError(_(
                    "Falta Libro, Folio o Consecutivo para: %s"
                ) % ', '.join(missing_libro_folio))

        vals_list = []
        for student in self.student_ids:
            libro = folio = consecutivo = False
            if not self.is_advanced:
                libro, folio, consecutivo = self._wk_get_libro_folio(student)
            vals_list.append({
                'student_id': student.id,
                'program_type_id': self.program_type_id.id,
                'grade_id': self.grade_id.id if not self.is_advanced else False,
                'sede_id': self.sede_id.id,
                'population_type': (
                    False if self.is_advanced else self.population_type),
                'populate_class_id': (
                    self.populate_class_id.id if self.is_advanced else False),
                'generation_mode': self.generation_mode,
                'intensidad_horaria': self.intensidad_horaria,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'fecha_expedicion': self.fecha_expedicion,
                'lugar_expedicion': self.lugar_expedicion,
                'libro': libro,
                'folio': folio,
                'consecutivo': consecutivo,
            })
        certificates = self.env['wk.school.colombo.certificate'].create(vals_list)

        report_xmlid = (
            'wk_school_colombo.certificate_avanzado_action' if self.is_advanced
            else 'wk_school_colombo.certificate_basico_intermedio_action')
        report = self.env.ref(report_xmlid)
        # Se guarda un ir.attachment propio por certificado (aunque el PDF
        # combinado sea el mismo para todo el lote en modalidad Grupal), para
        # que wk.school.colombo.certificate.action_download_pdf() pueda
        # reimprimir cada uno por separado después (2.21/2.22). No se usa el
        # mecanismo automático attachment=/attachment_use del
        # ir.actions.report porque exige que la plantilla marque cada
        # registro con data-oe-model/data-oe-id -el patrón de "varios
        # documentos en un solo PDF" de este módulo (igual que la tirilla de
        # pago) no los genera-.
        pdf_content, __ = report.sudo()._render_qweb_pdf(
            report.report_name, certificates.ids)
        for certificate in certificates:
            self.env['ir.attachment'].create({
                'name': 'Certificado - %s.pdf' % certificate.student_id.name,
                'datas': base64.b64encode(pdf_content),
                'res_model': certificate._name,
                'res_id': certificate.id,
                'mimetype': 'application/pdf',
            })
        return report.report_action(certificates)

    def action_view_history(self):
        """Botón "Ver histórico": consulta posterior de certificados ya
        generados (2.21/2.22), sin fragmentar la funcionalidad en un
        segundo ítem de menú (2.1 exige una única opción de menú)."""
        return {
            'type': 'ir.actions.act_window',
            'name': _("Histórico de Certificados generados"),
            'res_model': 'wk.school.colombo.certificate',
            'view_mode': 'list,form',
        }


class WkSchoolColomboCertificateWizardLine(models.TransientModel):
    """Libro/Folio/Consecutivo individual por estudiante (2.15): solo se usa
    cuando, en una generación grupal, esos valores varían por estudiante."""

    _name = 'wk.school.colombo.certificate.wizard.line'
    _description = 'Libro/Folio/Consecutivo por estudiante (Certificados)'

    wizard_id = fields.Many2one(
        'wk.school.colombo.certificate.wizard', required=True, ondelete='cascade')
    student_id = fields.Many2one(
        'student.student', string="Estudiante", required=True)
    libro = fields.Char(string="Libro")
    folio = fields.Char(string="Folio")
    consecutivo = fields.Char(string="Consecutivo")
