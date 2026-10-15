# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployee(models.Model):
    """Extiende hr.employee con campos biométricos de turnos."""
    _inherit = 'hr.employee'

    default_shift_id = fields.Many2one(
        'hr.shift',
        string='Turno por Defecto',
        help='Turno asignado habitual del empleado',
    )

    attendance_record_ids = fields.One2many(
        'hr.attendance.record',
        'employee_id',
        string='Registros de Asistencia',
    )
    attendance_record_count = fields.Integer(
        string='# Registros Asistencia',
        compute='_compute_attendance_record_count',
    )

    def _compute_attendance_record_count(self):
        for rec in self:
            rec.attendance_record_count = self.env['hr.attendance.record'].search_count([
                ('employee_id', '=', rec.id),
            ])

    def action_view_attendance_records(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registros de Asistencia',
            'res_model': 'hr.attendance.record',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
        }
