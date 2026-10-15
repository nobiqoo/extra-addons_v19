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


class DisciplineType(models.Model):
    _name = 'wk.discipline.type'
    _description = 'Discipline Type'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(default=1)


class StudentDiscipline(models.Model):
    _name = 'wk.student.discipline'
    _inherit = "wk.company.visibility.mixin"
    _description = 'Student Discipline'

    name = fields.Char(string='Title', required=True)
    student_id = fields.Many2one(
        'student.student', string="Student ", required=True)
    discipline_type = fields.Many2one(
        'wk.discipline.type', string="Discipline Type", required=True)
    summary = fields.Text(string='Summary')
    incident_date = fields.Date(
        string='Incident Date', default=fields.Date.context_today)
    class_timetable_id = fields.Many2one(
        'wk.class.timetable', string='Scheduled Class')
    enrollment_id = fields.Many2one(
        'student.enrollment', string="Enrollment No.", compute='_compute_enrollment', store=True)
    student_subject_id = fields.Many2one(
        'wk.student.subjects', string='Student Subject', domain="[('id', 'in',student_subject_id_domain)]")
    student_subject_id_domain = fields.Many2many(
        'wk.student.subjects', string='Student Subject ', compute='get_student_subject_domain')
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)

    @api.depends('student_id')
    def _compute_enrollment(self):
        for hours in self:
            if hours.student_id:
                enrollment = self.env['student.enrollment'].search(
                    [('student_id', '=', hours.student_id.id), ('state', '=', 'progress')], limit=1)
                hours.enrollment_id = enrollment
            else:
                hours.enrollment_id = False

    @api.depends('class_timetable_id')
    def get_student_subject_domain(self):
        for record in self:
            if record.class_timetable_id:
                class_record = self.env['wk.class.timetable'].search(
                    [('id', '=', record.class_timetable_id.id)])
                students = class_record.student_ids
                record.student_subject_id_domain = students
            else:
                record.student_subject_id_domain = False

    @api.onchange('student_subject_id')
    def _onchange_student_subject_id(self):
        for record in self:
            record.student_id = record.student_subject_id.student_id
