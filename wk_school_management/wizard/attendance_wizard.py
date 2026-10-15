# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class AttendanceWizard(models.TransientModel):

    _name = 'wk.attendance.wizard'
    _description = 'Attendance Wizard'

    fetch_entry_attendance = fields.Boolean(
        string='Fetch Entry Attendance Records?')

    def start_scheduled_class(self):
        active_id = self.env.context.get('active_id')
        class_record = self.env['wk.class.timetable'].browse(active_id)

        class_record.write({'state': 'running'})

        students = class_record.student_ids
        for student in students:
            entry_attendance = self.env['wk.student.attendance'].search(
                [('student_id', '=', student.student_id.id), ('attendance_date', '=', class_record.class_date)])
            if entry_attendance:
                values = {
                    'student_id': student.student_id.id,
                    'class_id': class_record.id,
                    'state': entry_attendance.attendance_state if self.fetch_entry_attendance else False,
                    'class_date': class_record.class_date,
                    'student_attendance_id': entry_attendance.id
                }
                self.env['wk.student.class.attendance'].create(values)
            else:
                vals = {
                    'student_id': student.student_id.id,
                    'attendance_date': class_record.class_date,
                    'attendance_state': 'absent',
                }
                entry_attendance = self.env['wk.student.attendance'].create(
                    vals)

                values = {
                    'student_id': student.student_id.id,
                    'class_id': class_record.id,
                    'state': entry_attendance.attendance_state if self.fetch_entry_attendance else False,
                    'class_date': class_record.class_date,
                    'student_attendance_id': entry_attendance.id
                }
                self.env['wk.student.class.attendance'].create(values)


class ClassAttendanceWizard(models.TransientModel):

    _name = 'wk.class.attendance.wizard'
    _inherit = 'wk.section.visibility.mixin'
    _description = 'Mark Class Attendance'

    class_attendance_ids = fields.Many2many(
        'wk.student.class.attendance', string="Class Attendance", domain="[('class_id','=',class_id )]")
    grade_id = fields.Many2one(
        "wk.school.grade", string="Grade", readonly=True)
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", readonly=True)
    class_date = fields.Date(string="Class Date", readonly=True)
    subject_id = fields.Many2one(
        'wk.grade.subjects', string='Subject', readonly=True)
    academic_year_id = fields.Many2one(
        'wk.academic.year', string='Academic Year', readonly=True)
    class_id = fields.Many2one('wk.class.timetable', string="Class")

    def confirm_class_attendance(self):
        for record in self:
            for attendance in record.class_attendance_ids:
                attendance.write({
                    'state': attendance.state,
                    'attendance_tag_ids': ([(6, 0, attendance.attendance_tag_ids.ids)]),
                })
                if attendance.student_attendance_id.attendance_state == 'absent':
                    attendance.student_attendance_id.attendance_state = attendance.state


class StudentTranscriptWizard(models.TransientModel):

    _name = 'wk.student.transcript.wizard'
    _description = 'Student Transcript'

    student_id = fields.Many2one('student.student', string='Student')
    session_id = fields.Many2one('wk.school.session', string='Session',
                                 domain="([('id','in',domain_session_ids)])", required=True)
    domain_session_ids = fields.Many2many(
        'wk.school.session', string="Session Domain", compute='_compute_student_enrolled_session')

    @api.depends('student_id')
    def _compute_student_enrolled_session(self):
        for record in self:
            if record.student_id.enrollment_ids:
                session_ids = record.student_id.enrollment_ids.mapped(
                    'session_id')
                record.domain_session_ids = session_ids
            else:
                record.domain_session_ids = False

    def fetch_student_transcript(self):
        self.ensure_one()
        return self.env.ref("wk_school_management.student_transcript_print").report_action(self, data={'session_id': self.session_id.id, 'student_id': self.student_id.id})
