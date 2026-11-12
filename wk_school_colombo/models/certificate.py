# -*- coding: utf-8 -*-
"""Histórico de Certificados académicos generados (tarea 12451).

Un registro por estudiante, incluso en una generación grupal (un único PDF
con varios certificados, pero un registro propio por estudiante): el
requerimiento (2.21/2.22) exige poder consultar después Libro, Folio y
Consecutivo de cada certificado emitido, y eso exige persistencia real -no
basta con el wizard (TransientModel), que se descarta tras usarse-.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .student_enrollment import POPULATION_TYPE_SELECTION

GENERATION_MODE_SELECTION = [
    ('individual', 'Individual'),
    ('grupal', 'Grupal'),
]


class WkSchoolColomboCertificate(models.Model):
    _name = 'wk.school.colombo.certificate'
    _description = 'Certificado académico generado'
    _order = 'create_date desc'

    student_id = fields.Many2one(
        'student.student', string="Estudiante", required=True, index=True)
    program_type_id = fields.Many2one(
        'wk.school.colombo.program.type', string="Programa / Módulo")
    grade_id = fields.Many2one('wk.school.grade', string="Nivel")
    sede_id = fields.Many2one('wk.school.colombo.sede', string="Sede")
    population_type = fields.Selection(
        POPULATION_TYPE_SELECTION, string="Tipo de población")
    # Solo para el certificado de Programa Avanzado: de ahí salen el nombre
    # del curso (title) y el Docente (teacher_id) que firma el certificado.
    populate_class_id = fields.Many2one(
        'wk.school.class', string="Clase ofertada (Avanzado)")
    generation_mode = fields.Selection(
        GENERATION_MODE_SELECTION, string="Modalidad de generación")
    intensidad_horaria = fields.Integer(string="Intensidad horaria (horas)")
    date_from = fields.Date(string="Fecha de inicio")
    date_to = fields.Date(string="Fecha de finalización")
    fecha_expedicion = fields.Date(string="Fecha de expedición", required=True)
    lugar_expedicion = fields.Char(string="Lugar de expedición")
    # Diligenciados manualmente por el usuario autorizado; Odoo no los
    # asigna ni calcula nunca (2.12-2.14). No aplican al certificado de
    # Programa Avanzado.
    libro = fields.Char(string="Libro")
    folio = fields.Char(string="Folio")
    consecutivo = fields.Char(string="Consecutivo")

    attachment_count = fields.Integer(
        string="PDF generados", compute='_compute_attachment_count')

    @api.depends('create_date')
    def _compute_attachment_count(self):
        for certificate in self:
            certificate.attachment_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', self._name), ('res_id', '=', certificate.id)])

    def action_download_pdf(self):
        """Descarga el PDF de este certificado.

        El adjunto lo crea wizard/certificate_wizard.py::
        action_generate_certificate() al generar el certificado (uno por
        estudiante, aun cuando la generación haya sido un único PDF
        combinado con otros estudiantes en modalidad Grupal).
        """
        self.ensure_one()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', self._name), ('res_id', '=', self.id)],
            limit=1, order='create_date desc')
        if not attachment:
            raise UserError(_(
                "No se encontró el PDF de este certificado."))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
