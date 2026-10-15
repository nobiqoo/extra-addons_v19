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
import logging

_logger = logging.getLogger(__name__)


class TermReport(models.Model):
    _name = 'wk.term.reports'
    _inherit = 'wk.section.visibility.mixin'
    _description = 'Term Report Card'

    student_subject_id = fields.Many2one(
        'wk.student.subjects', string=" Student")
    student_id = fields.Many2one(
        'student.student', related='student_subject_id.student_id')
    session_id = fields.Many2one('wk.school.session', 'Session')
    academic_year_id = fields.Many2one(
        'wk.academic.year', string="Academic Year")
    term_id = fields.Many2one('wk.grade.terms', string='Term')
    grade_id = fields.Many2one('wk.school.grade', string='Grade')
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", domain="[('grade_id', '=', grade_id)]")
    total_assignments = fields.Integer(
        string="Assignments", compute='_compute_term_assignment_count')
    point_obtained = fields.Integer(string="Current Points")
    subject_id = fields.Many2one('wk.grade.subjects', string="Subject")
    scale_line_id = fields.Many2one(
        'wk.grade.scale.line', string="Current Grades")

    @api.depends('term_id')
    def _compute_term_assignment_count(self):
        for record in self:
            if record.term_id:
                assignment_count = self.env['wk.student.assignment'].search_count(
                    [('student_subject_id', '=', record.student_subject_id.id), ('term_id', '=', record.term_id.id)])
                record.total_assignments = assignment_count
            else:
                record.total_assignments = 0
