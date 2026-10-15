# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class StudentAttendance(models.Model):

    _name = 'wk.student.attendance'
    _inherit = "wk.company.visibility.mixin"
    _description = 'Student Attendance'
    _order = "check_in desc"
    _rec_name = 'student_id'

    student_id = fields.Many2one('student.student', string=" Student", required=True)
    current_academic_year_id = fields.Many2one(
        string='Academic Year', related='student_id.current_enrollment_id.academic_year_id')
    attendance_date = fields.Date(
        string="Date", default=fields.Date.context_today,)
    attendance_state = fields.Selection([('present', 'Present'), (
        'absent', 'Absent')], string='Attendance Status', default='absent', required=True)
    class_attendance_ids = fields.One2many(
        'wk.student.class.attendance', 'student_attendance_id', string="Class Attendance")
    state = fields.Selection(
        [('new', 'New'), ('lock', 'Locked')], string="Status", default="new")
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    check_in = fields.Datetime(string="Check In")
    check_out = fields.Datetime(string="Check Out")
    total_hours_spent = fields.Float(compute='_compute_total_hours_spent',
                                     string="Total Hours")

    def lock_attendance(self):
        for attendance in self:
            if attendance.state != 'new':
                raise ValidationError(
                    _('Only new attendance can be marked as locked!'))
            attendance.state = 'lock'

    def unlink(self):
        for rec in self:
            if rec.state == 'lock':
                raise ValidationError(
                    _('Attendance in locked state cannot be deleted.')
                )
        return super().unlink()
    
    @api.constrains('attendance_date')
    def _check_attendance_date_not_future(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.attendance_date and rec.attendance_date > today:
                raise ValidationError(
                    _('Attendance cannot be created for a future date.')
                )
            
    @api.constrains('attendance_state', 'check_in', 'check_out')
    def _check_absent_with_check_times(self):
        for rec in self:
            if rec.attendance_state == 'absent' and (rec.check_in or rec.check_out):
                raise ValidationError(
                    _('Attendance cannot be marked as Absent when check-in or check-out time is set.')
                )

    @api.constrains('attendance_date', 'student_id')
    def _unique_attendance_date_wise(self):
        for record in self:
            attendance = self.search([
                ('attendance_date', '=', record.attendance_date),
                ('student_id', '=', record.student_id.id),
                ('id', '!=', record.id)])

            if attendance:
                raise ValidationError(
                    _(f"The attendance for {record.student_id.name} already exists for date {record.attendance_date}."))

    def student_attendance_create(self):
        today = fields.Date.today()
        if today.weekday() == 6:
            return True

        existing_attendance = self.search([('attendance_date', '=', today)])
        students = self.env['student.student'].search([('active', '=', True)])
        student_ids = {student.id for student in students}
        existing_student_ids = {attendance.student_id.id for attendance in existing_attendance}

        students_to_create = student_ids - existing_student_ids
        if students_to_create:
            self.env['wk.student.attendance'].create([{
                'student_id': student_id,
            } for student_id in students_to_create])

        attendances_to_lock = self.search([('state', '!=', 'lock'),
                                           ('attendance_date', '<', today)])
        if attendances_to_lock:
            attendances_to_lock.write({'state': 'lock'})
        return True

    def conv_time_float(self, value):
        return value.total_seconds() / 3600.0

    @api.depends('check_in', 'check_out')
    def _compute_total_hours_spent(self):
        for attendance in self:
            if attendance.check_in and attendance.check_out:
                difference = attendance.check_out - attendance.check_in
                total_hours = self.conv_time_float(difference)
                attendance.total_hours_spent = total_hours
            else:
                attendance.total_hours_spent = 0

    def get_kiosk_url(self):
        return self.get_base_url() + "/student_attendance/" + self.env.company.attendance_kiosk_key


class StudentPublicHolidays(models.Model):

    _name = 'wk.student.public.holidays'
    _description = 'Student Public Holidays'

    name = fields.Char(string='Title', required=True)
    date = fields.Date(string='Holiday Date', required=True)
