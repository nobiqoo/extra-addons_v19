# -*- coding: utf-8 -*-
from odoo import fields, models

from .student_enrollment import ACADEMIC_RESULT_SELECTION


class EnrollmentContinuityLog(models.Model):
    """Trazabilidad de Promoción y Finalización (2.23-2.25).
    """

    _name = 'wk.school.colombo.enrollment.continuity.log'
    _description = 'Trazabilidad de Promoción y Finalización'
    _order = 'create_date desc'

    student_id = fields.Many2one(
        'student.student', string="Estudiante", required=True, ondelete='cascade')
    origin_enrollment_id = fields.Many2one(
        'student.enrollment', string="Inscripción de origen",
        required=True, ondelete='cascade')
    academic_result = fields.Selection(
        ACADEMIC_RESULT_SELECTION, string="Resultado académico", required=True)
    origin_grade_id = fields.Many2one(
        'wk.school.grade', string="Nivel de origen", required=True)
    new_grade_id = fields.Many2one(
        'wk.school.grade', string="Nivel nuevo")
    target_session_id = fields.Many2one(
        'wk.school.session', string="Programación académica de destino")
    target_academic_year_id = fields.Many2one(
        'wk.academic.year', string="Año / periodo académico de destino")
    new_enrollment_id = fields.Many2one(
        'student.enrollment', string="Nueva inscripción")
    action_type = fields.Selection([
        ('promoted', 'Promovido'),
        ('finalized', 'Finalizado'),
    ], string="Acción", required=True)
    execution_type = fields.Selection([
        ('individual', 'Individual'),
        ('mass', 'Masiva'),
    ], string="Tipo de ejecución", required=True)
    user_id = fields.Many2one(
        'res.users', string="Usuario responsable",
        default=lambda self: self.env.user, required=True)
    student_vat = fields.Char(
        related='student_id.partner_id.vat', string="Identificación")
    student_program_type_id = fields.Many2one(
        related='student_id.program_type_id', string="Programa")
