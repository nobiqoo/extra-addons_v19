# -*- coding: utf-8 -*-
from odoo import fields, models

ACADEMIC_STATUS_SELECTION = [
    ('new', 'Nuevo'),
    ('activated', 'Activado'),
    ('released', 'Liberado'),
    ('postponed', 'Aplazado'),
]


class StudentAcademicStatusLog(models.Model):
    """Trazabilidad de cambios de Estado académico del estudiante.

    Un registro por cada cambio, automático o manual: estado anterior, estado
    nuevo, fecha (create_date), usuario responsable, tipo de cambio y motivo
    (solo aplica -y es obligatorio- en el aplazamiento manual).
    """

    _name = 'wk.school.colombo.student.status.log'
    _description = 'Histórico de estados académicos del estudiante'
    _order = 'create_date desc'

    student_id = fields.Many2one(
        'student.student', string="Estudiante", required=True, ondelete='cascade')
    state_from = fields.Selection(
        ACADEMIC_STATUS_SELECTION, string="Estado anterior")
    state_to = fields.Selection(
        ACADEMIC_STATUS_SELECTION, string="Estado nuevo", required=True)
    related_class_id = fields.Many2one(
        'wk.school.class', string="Clase ofertada relacionada", ondelete='set null')
    change_type = fields.Selection([
        ('automatic', 'Automático'),
        ('manual', 'Manual'),
    ], string="Tipo de cambio", required=True)
    reason = fields.Text(string="Motivo")
    user_id = fields.Many2one(
        'res.users', string="Usuario responsable",
        default=lambda self: self.env.user, required=True)
