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


class WkStudentSubjects(models.Model):

    _name = "wk.student.subjects"
    _inherit = ['wk.section.visibility.mixin', 'wk.company.visibility.mixin']
    _description = "Student Subjects"
    _order = "create_date desc"

    name = fields.Char(string='Name', readonly=True,
                       required=True, default=lambda self: _('New'))
    subject_id = fields.Many2one('wk.grade.subjects', string='Subject',
                                 domain="[('grade_id','=',grade_id )]", required=True)
    enrollment_id = fields.Many2one(
        'student.enrollment', 'Enrollment No.', ondelete='cascade')
    grade_id = fields.Many2one(
        'wk.school.grade', string='Grade', related='enrollment_id.grade_id', store=True)
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", related='enrollment_id.section_id', store=True)
    session_id = fields.Many2one(
        'wk.school.session', 'Session', related='enrollment_id.session_id', store=True)
    student_id = fields.Many2one(
        'student.student', 'Student', related='enrollment_id.student_id', store=True)
    student_image = fields.Image('Image', related='student_id.student_image')
    student_assignment_ids = fields.One2many(
        'wk.student.assignment', 'student_subject_id', string="Assignments")
    total_assignments = fields.Integer(
        string='Total Assignments', compute="_compute_assignment_count", store=True)
    academic_year_id = fields.Many2one(
        'wk.academic.year', related='enrollment_id.academic_year_id', store=True, string="Academic Year")
    company_id = fields.Many2one(
        'res.company', string="School", related='enrollment_id.company_id', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('progress', 'In Progress'),
        ('complete', 'Completed'),
    ], string='Status', default="draft", readonly=True)
    scale_id = fields.Many2one(
        'wk.grade.scales', related='subject_id.scale_id', string="Grade Scale", store=True)
    term_report_ids = fields.One2many(
        'wk.term.reports', 'student_subject_id', string="Term Report")
    scale_line_id = fields.Many2one(
        'wk.grade.scale.line', string="Current Grades", compute='compute_grade_term_report', store=True)
    credit_value = fields.Integer(related='subject_id.credit_value')
    subject_code = fields.Char(related='subject_id.subject_code')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                subject_id = vals.get('subject_id')
                subject = self.env['wk.grade.subjects'].browse(subject_id)
                enrollment_id = vals.get('enrollment_id')
                enrollment = self.env['student.enrollment'].browse(
                    enrollment_id)
                grade_id = enrollment.grade_id.id
                grade = self.env['wk.school.grade'].browse(grade_id)
                student_id = enrollment.student_id.id
                student = self.env['student.student'].browse(student_id)
                vals['name'] = str(student.name) + ' - ' + str(grade.name) + \
                    '(' + str(subject.name) + ')' or _('New')
        return super(WkStudentSubjects, self).create(vals_list)

    @api.constrains('subject_id', 'grade_id', 'session_id', 'enrollment_id')
    def check_for_unique_subject(self):
        for record in self:
            enrollment = self.search([
                ('subject_id', '=', record.subject_id.id),
                ('grade_id', '=', record.grade_id.id),
                ('enrollment_id', '=', record.enrollment_id.id),
                ('session_id', '=', record.session_id.id),
                ('id', '!=', record.id)])

            if enrollment:
                raise UserError(
                    _(f"Enrollment for {record.student_id.name} in subject '{record.subject_id.name}' already exists!"))

    @api.depends('student_assignment_ids')
    def _compute_assignment_count(self):
        for record in self:
            if record.student_assignment_ids:
                record.total_assignments = len(record.student_assignment_ids)
            else:
                record.total_assignments = 0

    def get_assigned_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assignments',
            'res_model': 'wk.student.assignment',
            'views': [(self.env.ref('wk_school_management.wk_student_assignment_tree').id, 'list'), (False, "form"),],
            'domain': [('student_subject_id', '=', self.id)]
        }

    @api.depends('student_assignment_ids.point_obtained')
    def compute_grade_term_report(self):
        for record in self:
            if record.scale_id.gpa_calculation:
                term_results = {}
                term_weightages = {}
                term_average_points = {}
                if record.student_assignment_ids:

                    for assignment in record.student_assignment_ids:
                        if assignment.exempted:
                            continue
                        populate_class = assignment.populate_class_id
                        term_id = assignment.term_id.id
                        type_id = assignment.type_id.id

                        if term_id not in term_results:
                            term_results[term_id] = {}
                            term_weightages[term_id] = assignment.term_id.weightage
                            term_average_points[term_id] = {
                                'total_points': 0.0, 'count': 0}
                        if type_id not in term_results[term_id]:
                            term_results[term_id][type_id] = {'total_points': 0.0,
                                                            'count': 0}
                        term_results[term_id][type_id]['total_points'] += assignment.percent_obtained
                        term_results[term_id][type_id]['count'] += 1
                        term_average_points[term_id]['total_points'] += assignment.point_obtained
                        term_average_points[term_id]['count'] += 1

                        weighted_percent = 0
                        num_terms = len(term_results)
                        for term_id, results in term_results.items():
                            term_weightage = term_weightages[term_id] if num_terms > 1 else 100
                            term_score = 0.0

                            for type_id, data in results.items():
                                assign_type = self.env['wk.class.assignment.type'].search(
                                    [('assignment_type_id', '=', type_id), ('populate_class_id', '=', populate_class.id)])
                                average_points = data['total_points']/data['count']
                                term_score += average_points * \
                                    (assign_type.weightage / 100)
                                term_scale_line = self.env['wk.grade.scale.line'].search([
                                    ('min_percent', '<=', term_score),
                                    ('max_percent', '>=', term_score),
                                    ('scale_id', '=', record.scale_id.id)])

                                term_report_id = self.env['wk.term.reports'].search(
                                    [('student_subject_id', '=', record.id), ('term_id', '=', term_id)])
                                term_report_id.scale_line_id = term_scale_line
                                term_report_id.point_obtained = term_scale_line.points

                            weighted_percent += term_score * (term_weightage/100)

                    scale_line = self.env['wk.grade.scale.line'].search([
                        ('min_percent', '<=', weighted_percent),
                        ('max_percent', '>=', weighted_percent),
                        ('scale_id', '=', record.scale_id.id)])

                    if scale_line:
                        record.scale_line_id = scale_line
                    else:
                        record.scale_line_id = False
