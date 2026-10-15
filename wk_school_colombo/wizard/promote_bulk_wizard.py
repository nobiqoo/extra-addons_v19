# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WkSchoolColomboPromoteBulkWizard(models.TransientModel):
    """Promoción / Finalización masiva de Inscripciones.

    Requerimiento "Resultado académico, Promoción y Finalización" (2.17-2.22):
    reemplaza el asistente compartido de Webkul -que aplica el mismo nivel a
    todo el lote- por uno con líneas, mismo patrón que
    wizard/bulk_class_wizard.py: cada línea (una Inscripción de origen) se
    valida y procesa de forma independiente, a diferencia de la creación
    masiva de Clases (todo-o-nada): aquí una línea inválida no cancela las
    demás, solo se excluye del proceso (2.22).
    """

    _name = 'wk.school.colombo.promote.bulk.wizard'
    _description = 'Promoción / Finalización masiva de Inscripciones'

    line_ids = fields.One2many(
        'wk.school.colombo.promote.bulk.line', 'wizard_id', string="Inscripciones")

    def action_process(self):
        self.ensure_one()
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "Solo un usuario autorizado (Officer o Admin) puede "
                "promover o finalizar inscripciones."))

        promoted = finalized = 0
        skipped_labels = []
        for line in self.line_ids:
            enrollment = line.enrollment_id
            student_name = enrollment.student_id.name
            if not enrollment or enrollment.continuity_action:
                skipped_labels.append(_(
                    "%s: ya fue procesada previamente") % student_name)
                continue
            if enrollment.academic_result == 'failed':
                skipped_labels.append(_("%s: No aprobado") % student_name)
                continue
            if enrollment.academic_result == 'pending':
                skipped_labels.append(_("%s: Pendiente") % student_name)
                continue

            if line.new_grade_id:
                if not (line.target_session_id and line.target_academic_year_id):
                    skipped_labels.append(_(
                        "%s: falta Programación académica o Año/periodo "
                        "académico de destino") % student_name)
                    continue
                fee_structure = self.env['fee.structure'].search(
                    [('grade_id', '=', line.new_grade_id.id)], limit=1)
                new_enrollment = self.env['student.enrollment'].create({
                    'student_id': enrollment.student_id.id,
                    'academic_year_id': line.target_academic_year_id.id,
                    'session_id': line.target_session_id.id,
                    'grade_id': line.new_grade_id.id,
                    'fee_structure_id': fee_structure.id,
                })
                enrollment._wk_mark_continuity(
                    action_type='promoted', execution_type='mass',
                    new_enrollment=new_enrollment)
                promoted += 1
            else:
                enrollment._wk_mark_continuity(
                    action_type='finalized', execution_type='mass')
                finalized += 1

        message = _(
            "Promovidos: %(promoted)s. Finalizados: %(finalized)s. "
            "No procesados: %(skipped)s.") % {
            'promoted': promoted, 'finalized': finalized,
            'skipped': len(skipped_labels)}
        if skipped_labels:
            message += "\n" + "\n".join(skipped_labels)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Resumen de Promoción / Finalización"),
                'message': message,
                'sticky': True,
            },
        }


class WkSchoolColomboPromoteBulkLine(models.TransientModel):
    """Una línea del asistente masivo = una Inscripción de origen."""

    _name = 'wk.school.colombo.promote.bulk.line'
    _description = 'Línea de Promoción / Finalización masiva'

    wizard_id = fields.Many2one(
        'wk.school.colombo.promote.bulk.wizard', required=True, ondelete='cascade')
    enrollment_id = fields.Many2one(
        'student.enrollment', string="Inscripción", required=True)
    student_id = fields.Many2one(
        related='enrollment_id.student_id', string="Estudiante")
    current_grade_id = fields.Many2one(
        related='enrollment_id.grade_id', string="Nivel actual")
    academic_result = fields.Selection(
        related='enrollment_id.academic_result', string="Resultado académico")
    new_grade_id = fields.Many2one('wk.school.grade', string="Nuevo nivel")
    target_session_id = fields.Many2one(
        'wk.school.session', string="Programación académica de destino",
        domain="[('state', '!=', 'complete')]")
    target_academic_year_id = fields.Many2one(
        'wk.academic.year', string="Año / periodo académico de destino",
        domain="[('session_id', '=', target_session_id)]")
    result_action = fields.Char(
        string="Acción", compute='_compute_result_action')
    validation_message = fields.Char(
        string="Resultado de validación", compute='_compute_result_action')

    @api.depends('enrollment_id.continuity_action', 'enrollment_id.academic_result',
                 'new_grade_id', 'target_session_id', 'target_academic_year_id')
    def _compute_result_action(self):
        for line in self:
            enrollment = line.enrollment_id
            if not enrollment or enrollment.continuity_action == 'promoted':
                line.result_action = _("Ya procesado")
                line.validation_message = _("Ya promovido")
                continue
            if enrollment.continuity_action == 'finalized':
                line.result_action = _("Ya procesado")
                line.validation_message = _("Ya finalizado")
                continue
            if enrollment.academic_result == 'failed':
                line.result_action = _("No elegible")
                line.validation_message = _("No aprobado")
                continue
            if enrollment.academic_result == 'pending':
                line.result_action = _("No elegible")
                line.validation_message = _("Pendiente")
                continue
            if line.new_grade_id:
                if not (line.target_session_id and line.target_academic_year_id):
                    line.result_action = _("No elegible")
                    if not line.target_session_id:
                        line.validation_message = _(
                            "Falta Programación académica de destino")
                    else:
                        line.validation_message = _(
                            "Falta Año/periodo académico de destino")
                    continue
                line.result_action = _("Promover")
                line.validation_message = _("Aprobado, listo para promover")
            else:
                line.result_action = _("Finalizar")
                line.validation_message = _("Aprobado, listo para finalizar")
