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
import logging

_logger = logging.getLogger(__name__)


class ClassAssignmentType(models.Model):

    _name = 'wk.class.assignment.type'
    _description = 'Class Assignment Type for Individual Classes'

    assignment_type_id = fields.Many2one(
        'wk.assignment.type', string="Type", required=True)
    weightage = fields.Float(string='Weightage(%)')
    populate_class_id = fields.Many2one('wk.school.class', string='Class')


class ClassAssignment(models.Model):

    _name = 'wk.class.assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'wk.section.visibility.mixin',
                'wk.company.visibility.mixin']
    _description = 'Class Assignment for all classes'

    name = fields.Char(string='Title', required=True)
    state = fields.Selection([
        ('new', 'New'),
        ('progress', 'In Progress'),
        ('complete', 'Completed'),
    ], string='Assignment Status', default="new", tracking=True)
    class_id = fields.Many2one(
        'wk.school.class', string='Class', readonly=True)
    grade_id = fields.Many2one(
        "wk.school.grade", string="Grade", readonly=True)
    section_id = fields.Many2one(
        "wk.grade.section", readonly=True, string="Section", domain="[('grade_id', '=', grade_id)]")
    subject_id = fields.Many2one('wk.grade.subjects', string='Subject',
                                 domain="[('grade_id', '=', grade_id)]", readonly=True)
    assignment_id = fields.Many2one('wk.grade.assignment', string='Assignment', required=True,
                                    domain="[('grade_id', '=', grade_id),('subject_id','=',subject_id),('state','=','approve')]")
    teacher_id = fields.Many2one('hr.employee', string='Teacher',
                                 domain="[('is_teacher','=',True),('subject_ids','=',subject_id)]")
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    total_marks = fields.Integer(string='Total Marks', required=True)
    scale_id = fields.Many2one(
        string="Grade Scale", related='subject_id.scale_id', store=True)
    student_assignment_ids = fields.One2many('wk.student.assignment', 'class_assignment_id',
                                             string='Students', domain="[('grade_id', '=', grade_id),('class_assignment_id','=',id)]")
    student_in_class = fields.Integer(
        related='class_id.total_enrolled', store="True")
    assignment_students = fields.Integer(
        string='Total Students', compute="_compute_assignment_students", store=True)
    attachment_ids = fields.Many2many(
        'wk.assignment.attachment', string="Attachments", readonly=True)
    description = fields.Html(string='Description',
                              related='assignment_id.description', store=True)
    type_id = fields.Many2one(
        'wk.assignment.type', related='assignment_id.type_id', string="Assignment Type", store=True)
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        assignments = super().create(vals_list)
        for assignment in assignments:
            assignment.attachment_ids = (
                [(6, 0, assignment.assignment_id.attachment_ids.ids)])
        return assignments

    def start_assignment(self):
        for obj in self:
            if obj.state != 'new':
                raise UserError(
                    _("Only new assignments are allowed to be started."))
            student_ids = obj.class_id.student_ids
            exist = self.env['wk.student.assignment'].search(
                [('class_assignment_id', '=', obj.id)])
            for student in student_ids:
                detail = {
                    'student_subject_id': student.id,
                    'grade_id': obj.grade_id.id,
                    'section_id': obj.section_id.id,
                    'start_date': obj.start_date,
                    'end_date': obj.end_date,
                    'assignment_id': obj.assignment_id.id,
                    'total_marks': obj.total_marks,
                    'class_assignment_id': obj.id,
                }
                if student not in exist.mapped('student_subject_id'):
                    self.env['wk.student.assignment'].create(detail)
                    report = self.env['wk.term.reports'].search(
                        [('student_subject_id', '=', student.id), ('term_id', '=', obj.class_id.term_id.id)])
                    student.state = 'progress'
                    if not report:
                        values = {
                            'student_subject_id': student.id,
                            'session_id': obj.class_id.session_id.id,
                            'academic_year_id': obj.class_id.academic_year_id.id,
                            'term_id': obj.class_id.term_id.id,
                            'subject_id': obj.subject_id.id,
                            'grade_id': obj.grade_id.id,
                            'section_id': obj.section_id.id,
                        }
                        self.env['wk.term.reports'].create(values)
            obj.state = 'progress'
        return True

    def complete_assignment(self):
        for obj in self:
            if obj.state != 'progress':
                raise UserError(
                    _("Only in progress assignments are allowed to be completed."))
            for assignment in obj.student_assignment_ids:
                if assignment.state == 'new' and not assignment.exempted:
                    raise UserError(
                        _("Not all the assignments are evaulated yet."))
                elif assignment.state == 'submit':
                    raise UserError(
                        _("Not all the assignments are evaulated yet."))
            obj.state = 'complete'
        return True

    def reset_assignment(self):
        for obj in self:
            obj.state = 'new'
        return True

    def evaluate_assignment(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "wk_school_management.wk_evaluation_wizard_action")
        submitted_by = self.env['wk.student.assignment'].search(
            [('state', '=', 'submit'), ('class_assignment_id', '=', self.id)])
        action['context'] = {
            'default_assignment_id': self.assignment_id.id,
            'default_grade_id': self.grade_id.id,
            'default_section_id': self.section_id.id,
            'default_subject_id': self.subject_id.id,
            'default_start_date': self.start_date,
            'default_end_date': self.end_date,
            'default_scale_id': self.scale_id.id,
            'default_total_marks': self.total_marks,
            'default_class_assignment_id': self.id,
            'default_student_assignment_ids': ([(6, 0, submitted_by.ids)])
        }
        return action

    @api.depends('student_assignment_ids')
    def _compute_assignment_students(self):
        for obj in self:
            if obj.student_assignment_ids:
                obj.assignment_students = len(obj.student_assignment_ids)
            else:
                obj.assignment_students = 0

    def add_new_students(self):
        for obj in self:
            student_ids = obj.class_id.student_ids
            exist = self.env['wk.student.assignment'].search(
                [('class_assignment_id', '=', obj.id)])
            for student in student_ids:
                detail = {
                    'student_subject_id': student.id,
                    'grade_id': obj.grade_id.id,
                    'section_id': obj.section_id.id,
                    'start_date': obj.start_date,
                    'end_date': obj.end_date,
                    'assignment_id': obj.assignment_id.id,
                    'total_marks': obj.total_marks,
                    'class_assignment_id': obj.id,
                }
                if student not in exist.mapped('student_subject_id'):
                    self.env['wk.student.assignment'].create(detail)
