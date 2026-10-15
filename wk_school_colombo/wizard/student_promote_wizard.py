# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StudentPromoteWizard(models.TransientModel):
    """Extiende el asistente "Promocionar ahora" (Webkul v5.0.4,
    wizard/enroll_wizard.py::StudentPromoteWizard).

    Requerimiento "Resultado académico, Promoción y Finalización" (2.9-2.16):
    el Nuevo nivel deja de ser obligatorio -con él se promueve, sin él se
    finaliza el proceso académico del estudiante-. La Finalización usa un
    paso propio (``step``) como pantalla de confirmación, mismo patrón ya
    usado en ``wk.enroll.wizard`` (duplicados) y en el asistente de Aplazar
    (wizard/student_postpone_wizard.py), en vez del atributo nativo
    ``confirm=`` de Odoo, para controlar el texto exacto y los botones.
    """

    _inherit = 'wk.student.promote'

    grade_id = fields.Many2one(required=False)
    session_id = fields.Many2one(required=False)
    academic_year_id = fields.Many2one(required=False)

    origin_enrollment_id = fields.Many2one(
        'student.enrollment', string="Inscripción de origen", readonly=True)
    academic_result = fields.Selection(
        related='origin_enrollment_id.academic_result', string="Resultado académico")
    step = fields.Selection([
        ('form', 'Formulario'),
        ('confirm_finalize', 'Confirmar finalización'),
    ], default='form')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and 'origin_enrollment_id' in fields_list:
            res['origin_enrollment_id'] = active_id
        return res

    def _wk_check_authorized(self):
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "Solo un usuario autorizado (Officer o Admin) puede "
                "promover o finalizar el proceso académico de un estudiante."))

    def _wk_reopen_action(self):
        """Reabre este mismo asistente (para avanzar a "confirm_finalize")."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wk.student.promote',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def promote_student(self):
        """Botón "Promover / Finalizar proceso".

        Con Nuevo nivel: valida Programación académica/Año-periodo destino
        (2.11, ya no obligatorios a nivel de campo) y delega en Webkul, que
        abre el formulario de la nueva inscripción ya prellenado -la marca
        de continuidad ("Promovido") ocurre al guardarlo, ver
        models/student_enrollment.py::create()-.

        Sin Nuevo nivel: no finaliza todavía -pasa a la pantalla de
        confirmación (2.14)-.
        """
        self.ensure_one()
        self._wk_check_authorized()
        origin = self.origin_enrollment_id
        if origin and origin.continuity_action:
            raise UserError(_(
                "La inscripción seleccionada ya fue procesada previamente."))

        if self.grade_id:
            if not (self.session_id and self.academic_year_id):
                raise UserError(_(
                    "Seleccione la Programación académica y el Año/periodo "
                    "académico de destino antes de promover."))
            return super().promote_student()

        self.step = 'confirm_finalize'
        return self._wk_reopen_action()

    def action_confirm_finalize(self):
        """Botón "Confirmar" de la pantalla de confirmación de Finalización."""
        self.ensure_one()
        self._wk_check_authorized()
        origin = self.origin_enrollment_id
        if not origin:
            return {'type': 'ir.actions.act_window_close'}
        if origin.continuity_action:
            raise UserError(_(
                "La inscripción seleccionada ya fue procesada previamente."))
        origin._wk_mark_continuity(
            action_type='finalized', execution_type='individual')
        return {'type': 'ir.actions.act_window_close'}
