# -*- coding: utf-8 -*-
from odoo import fields, models


class WkSchoolColomboGuardian(models.Model):
    """Línea de Acudiente, en la solicitud y/o en el estudiante.

    Requerimiento de campos académicos, pestaña "Acudiente": permite
    registrar varios acudientes (no solo un padre y una madre) con su
    información de contacto y parentesco. El mismo registro puede tener
    application_id y student_id diligenciados a la vez: al inscribir, el
    asistente de inscripción reasigna student_id sobre las líneas ya cargadas
    en la solicitud en lugar de duplicarlas, de modo que la información
    "se conserva" sin generar copias.
    """

    _name = 'wk.school.colombo.guardian'
    _description = 'Acudiente'
    _order = 'id'

    name = fields.Char(string="Nombre completo", required=True)
    landline_phone = fields.Char(string="Teléfono fijo")
    mobile = fields.Char(string="Celular")
    relationship = fields.Selection([
        ('padre', 'Padre'),
        ('madre', 'Madre'),
        ('abuelo_abuela', 'Abuelo/a'),
        ('tio_tia', 'Tío/a'),
        ('hermano_hermana', 'Hermano/a'),
        ('tutor_legal', 'Tutor legal'),
        ('otro', 'Otro'),
    ], string="Parentesco")
    relationship_other = fields.Char(
        string="¿Cuál parentesco?")
    email = fields.Char(string="Correo electrónico")
    application_id = fields.Many2one(
        'wk.application.form', string="Solicitud", ondelete='cascade')
    student_id = fields.Many2one(
        'student.student', string="Estudiante", ondelete='cascade')
