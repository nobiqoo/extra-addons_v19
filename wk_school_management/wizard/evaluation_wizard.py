# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class EvaluationWizard(models.TransientModel):

    _name = 'wk.evaluation.wizard'
    _inherit = 'wk.section.visibility.mixin'
    _description = 'Assignment Evaluation Wizard'

    assignment_id = fields.Many2one('wk.grade.assignment', string="Assignment", domain="[('state','=','approve')]")
    grade_id = fields.Many2one("wk.school.grade", string="Grade")
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", domain="[('grade_id', '=', grade_id)]")
    type_id = fields.Many2one(
        "wk.assignment.type", string='Assignment Type', related="assignment_id.type_id")
    subject_id = fields.Many2one("wk.grade.subjects", string='Subject')
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='Deadline')
    lowest_score = fields.Boolean(string="Lowest Score")
    total_marks = fields.Integer(string='Total Marks')
    scale_id = fields.Many2one(
        string="Grade Scale", related='subject_id.scale_id', store=True)
    class_assignment_id = fields.Many2one(
        'wk.class.assignment', string='Class Assignment', readonly=True)
    student_assignment_ids = fields.Many2many(
        'wk.student.assignment', string='Students')
    submitted_assignment_attachment = fields.Binary(string="Attachment")
    submit_comment = fields.Text(string="Comment")

    def submit_assignment(self):
        student_assignments_ids = self.env.context.get("active_ids")
        student_assignments = self.env['wk.student.assignment'].browse(
            student_assignments_ids)
        for student in student_assignments:
            if student.state == 'new':
                student.state = 'submit'

    def submit_score(self):
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids')

        if active_model == 'wk.student.assignment':
            student_assignments = self.env[active_model].browse(active_ids)

        elif active_model == 'wk.class.assignment':
            class_assignment = self.env[active_model].browse(active_ids)
            student_assignments = class_assignment.student_assignment_ids

        if len((self.student_assignment_ids)) == 0:
            raise UserError(_('No assignments selected for evaluation!'))

        for student in student_assignments:
            if student.state == 'new' and not self.lowest_score:
                raise UserError(_('No evaluation done because assignment is yet to be submitted!'))

            elif student.state == 'submit':
                if student.point_obtained > 0:
                    student.state = 'evaluate'
                if student.exempted:
                    student.state = 'evaluate'

            elif student.state == 'new' and self.lowest_score:
                scale_line = self.env['wk.grade.scale.line'].search(
                    [('scale_id', '=', self.scale_id.id)], order='min_percent', limit=1)
                if scale_line:
                    percent = scale_line.conversion_percent
                    marks_obtained = (percent * self.total_marks) / 100
                    point_obtained = scale_line.points
                    student.write({
                        'scale_line_id': scale_line,
                        'marks_obtained': marks_obtained,
                        'point_obtained': point_obtained,
                        'percent_obtained': percent,
                        'state': 'evaluate'
                    })
