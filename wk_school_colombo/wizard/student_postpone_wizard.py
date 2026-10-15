# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WkStudentPostponeWizard(models.TransientModel):
    """Aplazar estudiante (requerimiento "Estados académicos", 2.7-2.9).

    El propio formulario de este asistente -con el Motivo obligatorio y los
    botones Confirmar/Cancelar- es la ventana de confirmación que pide el
    requerimiento; no hace falta un paso de confirmación adicional encima.
    """

    _name = 'wk.school.colombo.student.postpone.wizard'
    _description = 'Aplazar estudiante'

    student_id = fields.Many2one('student.student', required=True)
    reason = fields.Text(string="Motivo", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and self.env.context.get('active_model') == 'student.student':
            res['student_id'] = active_id
        return res

    def action_confirm(self):
        """Requerimiento 2.7/2.16: solo un usuario autorizado puede aplazar."""
        self.ensure_one()
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "Solo un usuario autorizado (Officer o Admin) puede aplazar "
                "a un estudiante."))
        student = self.student_id
        student._wk_log_academic_status_change(
            'postponed', change_type='manual', reason=self.reason)
        student.academic_status = 'postponed'
        student._wk_schedule_accounting_activity(self.reason)
        return {'type': 'ir.actions.act_window_close'}
