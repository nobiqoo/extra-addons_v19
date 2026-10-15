# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import math

import logging

_logger = logging.getLogger(__name__)


class ClassTimetable(models.Model):

    _name = 'wk.class.timetable'
    _inherit = ['mail.thread', 'mail.activity.mixin', 
                'wk.section.visibility.mixin', 'wk.company.visibility.mixin']
    _description = 'Class Timetable'
    _order = "class_date asc"

    DAYS = [('monday', 'Monday'), ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'), ('thursday', 'Thursday'),
            ('friday', 'Friday'), ('saturday', 'Saturday'),
            ('sunday', 'Sunday')]

    name = fields.Char(string="Name", required=True, readonly=True)
    state = fields.Selection([
        ('draft', 'To Do'),
        ('running', 'Running'),
        ('complete', 'Completed'),
    ], string='Status', default="draft", tracking=True)
    grade_id = fields.Many2one('wk.school.grade', string="Grade")
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", domain="[('grade_id', '=', grade_id)]")
    teacher_id = fields.Many2one('hr.employee', string='Teacher', required=True,
                                 domain="[('is_teacher','=',True),('subject_ids','=',subject_id)]")
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    subject_id = fields.Many2one(
        'wk.grade.subjects', string='Subject', domain="[('grade_id', '=', grade_id)]")
    location_id = fields.Many2one('wk.class.location', string="Location")
    populate_class_id = fields.Many2one('wk.school.class', string="Class", ondelete='cascade')
    timeslot_id = fields.Many2one('wk.class.timeslot', string="Period")
    start_time = fields.Datetime(string="Start Time")
    end_time = fields.Datetime(string="End Time")
    term_id = fields.Many2one('wk.grade.terms', string="Term")
    class_date = fields.Date(string="Class Date")
    day = fields.Selection(DAYS, string="Day")
    session_id = fields.Many2one('wk.school.session', string='Session')
    lesson_plan_ids = fields.Many2many('wk.lesson.plan', string="Lesson Plans",
                                       domain="[('grade_id', '=', grade_id),('section_id', '=', section_id),('subject_id', '=', subject_id),('state','=','approve')]")
    student_ids = fields.Many2many(
        related='populate_class_id.student_ids', string='Students')
    class_assignments_ids = fields.Many2many(
        'wk.class.assignment', string='Assignments', compute='_compute_active_assignments')
    active = fields.Boolean(string="Active", default=True, 
                            help="Uncheck to archive the class.")

    def start_class(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(
                _('Only in draft status classes are allowed to be started'))

        action = {
            'type': 'ir.actions.act_window',
            'name': 'Start Class',
            'res_model': 'wk.attendance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'views': [[self.env.ref('wk_school_management.wk_attendance_wizard_view_form').id, 'form']],
        }
        return action

    def mark_completed(self):
        for obj in self:
            if obj.state != 'running':
                raise UserError(
                    _('Only running classes can be marked as done.'))
            obj.state = 'complete'

    def unlink(self):
        for timetable in self:
            if timetable.populate_class_id.state != 'new':
                raise ValidationError(
                    _('A schedule can only be deleted when the class is in "new" state.')
                )

        affected_schedules = self.mapped(
            lambda t: t.populate_class_id.weekly_schedule_ids.filtered(
                lambda ws:
                    ws.weekday == t.day and
                    ws.timeslot_id == t.timeslot_id and
                    ws.location_id == t.location_id
            )
        )

        res = super().unlink()

        for schedule in affected_schedules:
            exists = self.search_count([
                ('populate_class_id', '=', schedule.populate_class_id.id),
                ('day', '=', schedule.weekday),
                ('timeslot_id', '=', schedule.timeslot_id.id),
                ('location_id', '=', schedule.location_id.id),
            ])
            if not exists:
                schedule.state = 'new'

        return res

    def record_student_discipline(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'wk.discipline.wizard',
            'views': [(self.env.ref('wk_school_management.wk_discipline_wizard_form').id, 'form')],
            'context': {'default_class_timetable_id': self.id},
            'target': 'new'
        }
        return action

    def get_slot_time(self, start_time, calendar_time=None):
        factor = start_time < 0 and -1 or 1
        val = abs(start_time)
        hours, minutes = factor * \
            int(math.floor(val)), "{:0>2d}".format(int(round((val % 1) * 60)))
        tz = "AM"
        if calendar_time:
            final_calendar_time = str(hours).zfill(2) + ':' + str(minutes) + ':00'
            return final_calendar_time
        if minutes == 60:
            minutes = 0
            hours = hours + 1
        if hours >= 12:
            if hours > 12:
                hours = hours % 12
            tz = "PM"
        final_time = str(hours).zfill(2) + ':' + str(minutes) + ' ' + tz
        return final_time

    def mark_class_attendance(self):
        self.ensure_one()
        class_attendance_ids = self.env['wk.student.class.attendance'].search(
            [('class_id', '=', self.id)])

        action = {
            'type': 'ir.actions.act_window',
            'name': 'Mark Attendance',
            'res_model': 'wk.class.attendance.wizard',
            'views': [(self.env.ref('wk_school_management.wk_class_attendance_wizard_view_form').id, 'form')],
            'target': 'new',
            'context': {'default_grade_id': self.grade_id.id,
                        'default_section_id': self.section_id.id,
                        'default_class_date': self.class_date,
                        'default_subject_id': self.subject_id.id,
                        'default_academic_year_id': self.populate_class_id.academic_year_id.id,
                        'default_class_attendance_ids': ([(6, 0, class_attendance_ids.ids)]),
                        'default_class_id': self.id,
                        },
        }
        return action

    def get_class_attendance(self):
        return {
            'type': 'ir.actions.act_window',
            'name': ' Attendances',
            'res_model': 'wk.student.class.attendance',
            'views': [(self.env.ref('wk_school_management.wk_student_class_attendance_view_list').id, 'list'), (False, "form"),],
            'domain': [('student_id', 'in', self.student_ids.student_id.ids), ('class_date', '=', self.class_date)]
        }

    @api.depends('populate_class_id', 'class_date')
    def _compute_active_assignments(self):
        for record in self:
            if record.populate_class_id and record.class_date:
                assignments = self.env['wk.class.assignment'].search([
                    ('class_id', '=', record.populate_class_id.id)
                ])
                active_assignments = assignments.filtered(
                    lambda a: a.start_date <= record.class_date <= a.end_date)

                record.class_assignments_ids = active_assignments
            else:
                record.class_assignments_ids = False

    @api.model
    def fetch_data_for_dashboard(self, date_range=None, **kwarg):
        fetch_data = {}
        upcoming_classes = self.env['wk.class.timetable'].search([
                    ('class_date', '>=', date_range['start_date']),
                    ('class_date', '<=', date_range['end_date']),
                    ('active', '=', True),
                    ('state', '=', 'draft')])

        completed_classes = self.env['wk.class.timetable'].search([
                    ('class_date', '>=', date_range['start_date']),
                    ('class_date', '<=', date_range['end_date']),
                    ('active', '=', True),
                    ('state', '=', 'complete')])

        to_do_assignments = self.env['wk.student.assignment'].search([('state', '=', 'new')])
        completed_assignments = self.env['wk.student.assignment'].search(['|', ('state', '=', 'submit'), ('state', '=', 'evaluate')])

        fetch_data.update({'upcoming_classes': len(upcoming_classes),
                           'upcoming_classes_ids': upcoming_classes,
                           'completed_classes': len(completed_classes),
                           'completed_classes_ids': completed_classes,
                           'to_do_assignments': len(to_do_assignments),
                           'to_do_assignments_ids': to_do_assignments.ids,
                           'completed_assignments': len(completed_assignments),
                           'completed_assignments_ids': completed_assignments.ids,})
        return fetch_data
    
    def postpone_class(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Postpone Class'),
            'res_model': 'wk.timetable.postpone.wizard',
            'views': [[self.env.ref('wk_school_management.view_timetable_postpone_wizard_form').id, 'form']],
            'target': 'new',
            'context': {
                'default_timetable_id': self.id,
                'default_class_date': self.class_date,
                'default_timeslot_id': self.timeslot_id.id,
                'default_location_id': self.location_id.id,
            }
        }
    
    def _check_location_availability(self, date, day, timeslot, location):
        self.ensure_one()

        domain = [
            ('id', '!=', self.id),
            ('class_date', '=', date),
            ('day', '=', day),
            ('location_id', '=', location.id),
            '|', '|',
            '&', ('timeslot_id.start_time', '<=', timeslot.start_time),
            ('timeslot_id.end_time', '>', timeslot.start_time),
            '&', ('timeslot_id.start_time', '<', timeslot.end_time),
            ('timeslot_id.end_time', '>=', timeslot.end_time),
            '&', ('timeslot_id.start_time', '>=', timeslot.start_time),
            ('timeslot_id.end_time', '<=', timeslot.end_time),
        ]

        conflict = self.search(domain, limit=1)
        if conflict:
            raise ValidationError(
                _(
                    '%s is already booked on %s (%s) during %s.'
                ) % (
                    location.name,
                    date,
                    day.capitalize(),
                    timeslot.name
                )
            )

    def _compute_display_name_with_date(self, class_date):
        self.ensure_one()
        grade = self.grade_id.name or ""
        title = self.populate_class_id.title or ""
        subject = self.subject_id.name or ""
        return f"{grade}{title}-{subject}({class_date})"
