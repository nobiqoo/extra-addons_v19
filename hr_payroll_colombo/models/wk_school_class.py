# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WkSchoolClass(models.Model):
    _inherit = 'wk.school.class'

    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Cuenta Analítica',
        help='Cuenta analítica origen del curso. Las horas que el profesor '
             'dicte en esta clase se llevan a nómina con esta cuenta.')
    attendance_ids = fields.One2many(
        comodel_name='hr.attendance', inverse_name='school_class_id',
        string='Asistencias')
    attendance_count = fields.Integer(
        string='Asistencias', compute='_compute_attendance_totals')
    payroll_hours_total = fields.Float(
        string='Horas Aprobadas', compute='_compute_attendance_totals',
        help='Horas aprobadas para nómina que se han registrado en el curso.')

    @api.depends('attendance_ids.payroll_hours',
                 'attendance_ids.approved_for_payroll')
    def _compute_attendance_totals(self):
        grouped = self.env['hr.attendance']._read_group(
            [('school_class_id', 'in', self.ids)],
            groupby=['school_class_id', 'approved_for_payroll'],
            aggregates=['__count', 'payroll_hours:sum'])
        counts = {}
        approved_hours = {}
        for school_class, approved, count, hours in grouped:
            counts[school_class.id] = counts.get(school_class.id, 0) + count
            if approved:
                approved_hours[school_class.id] = (
                    approved_hours.get(school_class.id, 0.0) + (hours or 0.0))
        for record in self:
            record.attendance_count = counts.get(record.id, 0)
            record.payroll_hours_total = approved_hours.get(record.id, 0.0)

    def action_view_attendances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Asistencias de {self.display_name}',
            'res_model': 'hr.attendance',
            'view_mode': 'list,form',
            'domain': [('school_class_id', '=', self.id)],
            'context': {'default_school_class_id': self.id},
        }
