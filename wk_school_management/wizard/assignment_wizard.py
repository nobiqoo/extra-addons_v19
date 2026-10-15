# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

import logging

_logger = logging.getLogger(__name__)


class AssignmentWizard(models.TransientModel):

    _name = 'wk.assignment.wizard'
    _inherit = 'wk.section.visibility.mixin'
    _description = 'Assignment Wizard'

    name = fields.Char(string="Assignment Title", required=True)
    grade_id = fields.Many2one(
        "wk.school.grade", string="Grade", readonly=True)
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", readonly=True)
    subject_id = fields.Many2one(
        'wk.grade.subjects', string='Subject', readonly=True)
    class_id = fields.Many2one(
        'wk.school.class', string='Class', readonly=True)
    assignment_id = fields.Many2one('wk.grade.assignment', string='Assignment', required=True,
                                    domain="[('grade_id','=',grade_id),('subject_id','=',subject_id),('type_id','=',type_id),('state','=','approve')]")
    start_date = fields.Date(
        string='Start Date', required=True, default=fields.Date.context_today)
    end_date = fields.Date(string='End Date', required=True,  default=lambda self: fields.Date.context_today(self) + timedelta(days=1))
    total_marks = fields.Integer(string='Total Marks', required=True)
    type_id = fields.Many2one("wk.assignment.type", string='Assignment Type',
                              required=True, domain="[('id', 'in',type_ids_domain )]")
    type_ids_domain = fields.Many2many(
        "wk.assignment.type", string='Assignment Type Domain', compute='_get_assignment_type_domain')
    no_of_days = fields.Integer(string='No. of Days', required=True, default=1)

    @api.constrains('start_date', 'end_date')
    def _check_for_assignment_duration(self):
        for assignment in self:
            class_id = assignment.class_id
            if assignment.start_date > assignment.end_date:
                raise UserError(
                    _('End date for assignment should be after the start date!!'))

            if assignment.start_date and assignment.end_date:
                if (assignment.start_date < class_id.start_date
                        or assignment.start_date > class_id.end_date) or (
                        assignment.end_date < class_id.start_date
                        or assignment.end_date > class_id.end_date):

                    raise UserError(
                        _("The duration is invalid. Assignment dates should lie within the term's duration."))
        return True

    @api.constrains('total_marks')
    def _check_total_marks_for_assignment(self):
        for assignment in self:
            if assignment.total_marks == 0:
                raise UserError(_("Weightage for the assignment cannot be 0."))

    @api.constrains('no_of_days')
    def _check_no_of_days(self):
        for assignment in self:
            if assignment.no_of_days <= 0:
                raise UserError(_("No of days for the assignment should be greater than 0."))

    def assign_now(self):
        self.ensure_one()
        details = {
            'name': self.name,
            'class_id': self.class_id.id,
            'teacher_id': self.class_id.teacher_id.id,
            'assignment_id': self.assignment_id.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'total_marks': self.total_marks,
            'grade_id': self.grade_id.id,
            'section_id': self.section_id.id,
            'subject_id': self.subject_id.id,
        }
        assignment_id = self.env['wk.class.assignment'].create(details)
        action = action = {
            'type': 'ir.actions.act_window',
            'name': 'Class Assignment',
            'res_model': 'wk.class.assignment',
            'view_mode': 'form',
            'res_id': assignment_id.id,
            'views': [[self.env.ref('wk_school_management.class_assignment_form').id, 'form']],
        }
        return action

    @api.depends('class_id')
    def _get_assignment_type_domain(self):
        for record in self:
            if record.class_id:
                assignment_type = record.class_id.class_assignment_type_ids.assignment_type_id
                record.type_ids_domain = assignment_type
            else:
                record.type_ids_domain = False

    @api.onchange('start_date')
    def _onchange_assignment_start_date(self):
        if self.start_date > self.end_date:
            raise UserError(
                _('Start date for assignment should be before the end date!!'))

        if self.start_date and not self.env.context.get('assignment'):
            self.with_context(assignment=1).write({
                'end_date': self.start_date + timedelta(days=self.no_of_days)
            })

    @api.onchange('end_date')
    def _onchange_assignment_end_date(self):
        if self.start_date > self.end_date:
            raise UserError(
                _('End date for assignment should be after the start date!!'))

        if self.end_date and not self.env.context.get('assignment'):
            self.with_context(assignment=1).write({
                'no_of_days': (self.end_date - self.start_date).days
            })

    @api.onchange('no_of_days')
    def _onchange_assignment_no_of_days(self):
        if self.end_date and not self.env.context.get('assignment'):
            self.with_context(assignment=1).write({
                'end_date': self.start_date + timedelta(days=self.no_of_days)
            })


class DisciplineWizard(models.TransientModel):

    _name = 'wk.discipline.wizard'
    _description = 'Discipline Wizard'

    name = fields.Char(string='Title', required=True)
    discipline_type = fields.Many2one(
        'wk.discipline.type', string="Discipline Type", required=True)
    incident_date = fields.Date(
        string='Incident Date', default=fields.Date.context_today)
    summary = fields.Text(string='Summary')
    class_timetable_id = fields.Many2one(
        'wk.class.timetable', string='Scheduled Class')
    student_ids = fields.Many2many('student.student', string='Students',
        domain="[('id', 'in',student_ids_domain)]")
    student_ids_domain = fields.Many2many('student.student',
        compute='_compute_student_ids_domain')

    @api.depends('class_timetable_id')
    def _compute_student_ids_domain(self):
        for rec in self:
            if rec.class_timetable_id:
                students = rec.class_timetable_id.student_ids.mapped('student_id')
                rec.student_ids_domain = students
            else:
                rec.student_ids_domain = self.env['student.student']

    def assign_discipline(self):
        for student in self.student_ids:
            self.env['wk.student.discipline'].create({
                'name': self.name,
                'student_id': student.id,
                'discipline_type': self.discipline_type.id,
                'summary': self.summary,
                'incident_date': self.incident_date,
                'class_timetable_id': self.class_timetable_id.id,
            })
