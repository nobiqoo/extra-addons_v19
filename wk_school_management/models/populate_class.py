# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class PopulateClass(models.Model):

    _name = 'wk.school.class'
    _inherit = ['mail.thread', 'mail.activity.mixin', 
                'wk.section.visibility.mixin',
                'wk.company.visibility.mixin']
    _description = 'Populate Class'
    _order = "create_date desc"

    name = fields.Char(string='Class', required=True,
                       default=lambda self: _('New'), readonly=True)
    title = fields.Char(string='Title', required=True, copy=False)
    state = fields.Selection([
        ('new', 'New'),
        ('confirm', 'Confirmed'),
        ('complete', 'Completed'),
    ], string=' Class Status', default="new", tracking=True)
    grade_id = fields.Many2one(
        'wk.school.grade', string='Grade', required=True, copy=False)
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", domain="[('grade_id', '=', grade_id)]")
    session_id = fields.Many2one(
        'wk.school.session', string='Session', required=True)
    academic_year_id = fields.Many2one(
        'wk.academic.year', string='Academic Year', domain="[('session_id', '=', session_id)]")
    term_id = fields.Many2one('wk.grade.terms', string='Term',
                              domain="[('academic_year_id', '=', academic_year_id)]", required=True, ondelete='cascade')
    teacher_id = fields.Many2one('hr.employee', string='Teacher', required=True,
                                 domain="[('is_teacher','=',True),('subject_ids','=',subject_id)]")
    teacher_ids = fields.Many2many('hr.employee', string='Secondary Teachers',
                                   domain="[('is_teacher','=',True),('subject_ids','=',subject_id),('id','!=',teacher_id)]")
    subject_id = fields.Many2one('wk.grade.subjects', string='Subject',
                                 required=True, domain="[('grade_id', '=', grade_id)]")
    start_date = fields.Date(
        string="Start From", related='term_id.start_date', store=True, readonly=False)
    end_date = fields.Date(
        string="End Till", related='term_id.end_date', store=True, readonly=False)
    capacity = fields.Integer(string='Total Capacity', required=True)
    student_ids = fields.Many2many(
        'wk.student.subjects', string='Students', domain="[('id', 'in',student_ids_domain )]")
    student_ids_domain = fields.Many2many(
        'wk.student.subjects', string='Student Domain', compute='get_student_ids_domain')
    total_enrolled = fields.Integer(
        string='Total Enrolled', compute="_compute_enrolled_students", store=True)
    unit_credit = fields.Float(string="Unit Credit")
    weekly_schedule_ids = fields.One2many(
        'wk.weekly.schedule', 'populate_class_id', string="Weekly Schedule")
    timetable_ids = fields.One2many(
        'wk.class.timetable', 'populate_class_id', string='Timetable')
    timetable_count = fields.Integer(
        string='Class Count', compute='_compute_timetable_count')
    assignment_count = fields.Integer(
        string='Assignment Count', compute='_compute_assignment_count')
    class_assignment_type_ids = fields.One2many(
        'wk.class.assignment.type', 'populate_class_id', string='Assignment Type')
    divide_assignment_weightage = fields.Boolean(
        string='Want to divide assignment weightage equally?')
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)

    @api.depends('student_ids')
    def _compute_enrolled_students(self):
        for obj in self:
            if obj.student_ids:
                obj.total_enrolled = len(obj.student_ids)
            else:
                obj.total_enrolled = 0

    @api.depends('subject_id', 'grade_id', 'session_id', 'academic_year_id', 'section_id')
    def get_student_ids_domain(self):
        for record in self:
            if record.grade_id and record.subject_id and record.academic_year_id:
                base_domain = [('grade_id', '=', record.grade_id.id),
                                ('subject_id', '=', record.subject_id.id),
                                ('term_id', '=', record.term_id.id)]
                if record.section_id:
                    base_domain.append(('section_id', '=', record.section_id.id))
                excluded_students = self.search(
                    base_domain + [('id', '!=', record._origin.id)]).mapped('student_ids.id')

                student_domain = [
                    ('grade_id', '=', record.grade_id.id),
                    ('subject_id', '=', record.subject_id.id),
                    ('session_id', '=', record.session_id.id),
                    ('academic_year_id', '=', record.academic_year_id.id),
                    ('id', 'not in', excluded_students)]

                if record.section_id:
                    student_domain.append(('section_id', '=', record.section_id.id))
                students = self.env['wk.student.subjects'].search(student_domain)
                record.student_ids_domain = students
            else:
                record.student_ids_domain = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                subject_id = vals.get('subject_id')
                subject = self.env['wk.grade.subjects'].browse(subject_id)
                grade_id = vals.get('grade_id')
                grade = self.env['wk.school.grade'].browse(grade_id)
                title = vals.get('title')
                vals['name'] = str(
                    subject.name) + '-' + str(grade.name) + '(' + str(title) + ')' or _('New')

        grades = super(PopulateClass, self).create(vals_list)
        for grade in grades:
            if grade.capacity < len(grade.student_ids):
                enrolled_students = len(grade.student_ids)
                raise ValidationError(
                    _("Sorry, maximum capacity cannot be less than enrolled students, remove enrolled students and then change the capacity!!! \n Total %s students enrolled right now.", enrolled_students))

            if grade.divide_assignment_weightage:
                total_types = len(grade.class_assignment_type_ids)
                if total_types != 0:
                    assignment_weightage = (100 / total_types)
                    for assignment in grade.class_assignment_type_ids:
                        assignment.weightage = assignment_weightage
        return grades

    def write(self, vals):
        if vals.get('subject_id'):
            subject_id = vals.get('subject_id')
            subject = self.env['wk.grade.subjects'].browse(subject_id)
            vals['name'] = str(subject.name) + '-' + \
                str(self.grade_id.name) + '(' + str(self.title) + ') '
        elif vals.get('grade_id'):
            grade_id = vals.get('grade_id')
            grade = self.env['wk.school.grade'].browse(grade_id)
            vals['name'] = str(self.subject_id.name) + '-' + \
                str(grade.name) + '(' + str(self.title) + ') '
        elif vals.get('title'):
            title = vals.get('title')
            vals['name'] = str(self.subject_id.name) + '-' + \
                str(self.grade_id.name) + '(' + str(title) + ') '

        res = super().write(vals)
        if self.capacity < len(self.student_ids):
            enrolled_students = len(self.student_ids)
            raise ValidationError(
                _("Sorry, maximum capacity cannot be less than enrolled students, remove enrolled students and then change the capacity!!! \n Total %s students enrolled right now.", enrolled_students))

        if self.divide_assignment_weightage:
            total_types = len(self.class_assignment_type_ids)
            if total_types != 0:
                assignment_weightage = (100 / total_types)
                for assignment in self.class_assignment_type_ids:
                    assignment.weightage = assignment_weightage
        return res

    def unlink(self):
        for record in self:
            if record.state == 'confirm':
                raise UserError(
                    _('A class already confirmed cannot be deleted. You can reset it if needed.')
                )

        schedules = self.mapped('weekly_schedule_ids')
        res = super().unlink()

        for schedule in schedules:
            if not self.search_count([('weekly_schedule_ids', 'in', schedule.id)]):
                schedule.state = 'new'
        return res

    @api.constrains('start_date', 'end_date')
    def _check_for_duration(self):
        for classes in self:
            if classes.start_date > classes.end_date:
                raise ValidationError(_
                                      ('Error!\n The duration of term is invalid.'))
        return True

    @api.onchange('grade_id')
    def onchange_grade_id(self):
        self.teacher_id = False
        self.subject_id = False
        self.term_id = False
        self.student_ids = False

    @api.onchange('subject_id')
    def onchange_subject_id(self):
        self.teacher_id = False
        self.student_ids = False

    @api.onchange('session_id')
    def onchange_session_id(self):
        self.term_id = False
        self.academic_year_id = False

    @api.onchange('academic_year_id')
    def onchange_academic_year_id(self):
        self.term_id = False

    def confirm_class(self):
        for obj in self:
            if obj.state != 'new':
                raise UserError(
                    _("Classes only in new stage are allowed to be started."))

            if not obj.class_assignment_type_ids:
                raise UserError(_("Add assignment types and their weightage."))

            total = 0
            for type in obj.class_assignment_type_ids:
                total += type.weightage
            if total != 100:
                raise UserError(
                    _("Please make sure to make assignment type weightage sum to be 100%."))
            obj.state = 'confirm'
        return True

    def reset_class(self):
        for obj in self:
            if obj.state != 'confirm':
                raise UserError(
                    _("Classes only in confirmed stage are allowed to be reset."))
            obj.state = 'new'
        return True

    def complete_class(self):
        self.ensure_one()
        assigned_types = set(self.env['wk.class.assignment'].search([
            ('class_id', '=', self.id)]).mapped('type_id.id'))
        required_types = set(self.class_assignment_type_ids.mapped('assignment_type_id.id'))

        missing_types = required_types - assigned_types
        if missing_types:
            missing_names = self.env['wk.assignment.type'].browse(list(missing_types)).mapped('name')
            raise ValidationError(
                _("All assignment types must be assigned before completing the class.\nMissing: %s") % ", ".join(missing_names)
            )
        if not self.end_date < date.today():
            raise ValidationError(_("Class can only be marked as completed once the duration of the class gets over."))
        self.state = 'complete'

    def schedule_class(self):
        self.ensure_one()
        if not self.weekly_schedule_ids:
            raise UserError(_("Please setup the weekly schedule first!!"))

        return {
            'type': 'ir.actions.act_window',
            'name': ' Confirm Schedule',
            'res_model': 'wk.confirm.timetable',
            'target': 'new',
            'views': [(self.env.ref('wk_school_management.timetable_wizard_view_form').id, 'form'), (False, "list"),],
            'context': {
                'default_weekly_schedule_ids': self.weekly_schedule_ids.ids,
                'default_name': self.name,
                'default_grade_id': self.grade_id.id,
                'default_section_id': self.section_id.id,
                'default_start_date': self.start_date,
                'default_end_date': self.end_date,
                'default_subject_id': self.subject_id.id,
            }}

    def get_scheduled_classes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': ' Classes Scheduled',
            'res_model': 'wk.class.timetable',
            'view_mode': 'list,form,calendar',
            'domain': [('populate_class_id', '=', self.id)]
        }

    def assign_assignment(self):
        self.ensure_one()
        if self.start_date > date.today() or self.end_date < date.today():
            raise ValidationError(
                _('Assignment can only be assigned within the term.'))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Class Assignment',
            'res_model': 'wk.assignment.wizard',
            'views': [(self.env.ref('wk_school_management.assignment_wizard_form').id, 'form'), (False, "list"),],
            'target': 'new',
            'context': {
                'default_class_id': self.id,
                'default_grade_id': self.grade_id.id,
                'default_section_id': self.section_id.id,
                'default_subject_id': self.subject_id.id
            }
        }

    def get_assigned_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assignments',
            'res_model': 'wk.class.assignment',
            'views': [(self.env.ref('wk_school_management.class_assignment_tree').id, 'list'), (False, "form"),],
            'domain': [('class_id', '=', self.id)]
        }

    def _compute_assignment_count(self):
        for obj in self:
            obj.assignment_count = self.env['wk.class.assignment'].search_count(
                [('class_id', '=', obj.id)])

    @api.depends('timetable_ids')
    def _compute_timetable_count(self):
        for timetable in self:
            if timetable.timetable_ids:
                timetable.timetable_count = len(timetable.timetable_ids)
            else:
                timetable.timetable_count = 0

    @api.constrains('class_assignment_type_ids')
    def _check_for_type_weightage(self):
        for type in self:
            total = 0
            for weightage in type.class_assignment_type_ids:
                total += weightage.weightage

            if total > 100:
                raise ValidationError(
                    _("Total weightage of all the assignment types cannot be greater than 100% !!"))
            elif total < 100 and not type.divide_assignment_weightage:
                raise ValidationError(
                    _("Total weightage of all the assignment types should be 100% !!"))
            elif total == 0 and not type.divide_assignment_weightage:
                raise ValidationError(
                    _("Total weightage of all the assignment types should be 100% !!"))

    def get_populate_class_record(self, session, grade, section):
        domain = [('session_id', '=', session),('grade_id', '=', grade)]
        if section:
            domain.append(('section_id', '=', section))
        classes = self.search(domain)
        populate_class = [(class_id.id, class_id.name)for class_id in classes]
        return populate_class

    def fetch_gradesheet_record(self, populate_class):
        populate_class = self.browse(populate_class)
        students = []
        assignment = []
        assignment_score = []
        average = []
        col_average = []
        col_dict = {}
        col_sum = 0
        student_len = len(populate_class.student_ids)

        for assignment_type in populate_class.class_assignment_type_ids:
            assignment_weightage = round(assignment_type.weightage, 2)
            assignment_detail = (
                assignment_type.assignment_type_id.name, assignment_weightage)
            assignment.append(assignment_detail)
            type_id = assignment_type.assignment_type_id.name

            if type_id not in col_dict:
                col_dict[type_id] = 0.0
        for student in populate_class.student_ids:
            student_detail = (student.student_id.id, student.student_id.name)
            students.append(student_detail)
            score = student.student_assignment_ids.get_gradesheet_record(
                populate_class, student)
            for val in score[0]:
                if val[0] in col_dict:
                    col_dict[val[0]] += val[1]

            if len(col_dict) == len(score[0]):
                for ele in score[0]:
                    value = (student.student_id.name, ele)
                    assignment_score.append(value)
            else:
                for key in col_dict:
                    for result in score[0]:
                        if result[0] != key:
                            ele = (key, 0)
                            res = (student.student_id.name, ele)
                            assignment_score.append(res)
                        else:
                            value = (student.student_id.name, result)
                            assignment_score.append(value)

            if len(score[1]) >= 1:
                average.append(
                    (student.student_id.name, round(score[1][-1], 2)))
            else:
                average.append((student.student_id.name, 0))

        for key, value in col_dict.items():
            avg = round(value / student_len, 2) if student_len > 0 else 0
            col_average.append((key, avg))

        for ele in average:
            col_sum += ele[1]

        last_col = round(col_sum / student_len, 2) if student_len > 0 else 0
        return students, assignment, assignment_score, average, col_average, last_col
