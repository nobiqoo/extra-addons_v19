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
import logging
import base64
from odoo.tools.mimetypes import guess_mimetype


_logger = logging.getLogger(__name__)


class StudentAssignment(models.Model):

    _name = 'wk.student.assignment'
    _description = 'Student Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 
                'wk.section.visibility.mixin', 'wk.company.visibility.mixin']
    _order = "create_date desc"

    state = fields.Selection([
        ('new', 'New'),
        ('submit', 'Submitted'),
        ('evaluate', 'Evaluated')
    ], string='Status', default="new", readonly=True, tracking=True)
    student_subject_id = fields.Many2one(
        'wk.student.subjects', string='Student  ', domain="[('id', 'in',student_subject_id_domain )]", required=True, ondelete='cascade')
    student_subject_id_domain = fields.Many2many(
        'wk.student.subjects', compute='_get_student_subject_id')
    student_id = fields.Many2one(
        'student.student', readonly=True, related='student_subject_id.student_id', store=True)
    subject_id = fields.Many2one(
        'wk.grade.subjects', readonly=True, related='student_subject_id.subject_id', store=True)
    company_id = fields.Many2one(
        'res.company', string="School", required=True, default=lambda self: self.env.company)
    grade_id = fields.Many2one(
        'wk.school.grade', string="Grade", required=True)
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", domain="[('grade_id', '=', grade_id)]")
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    assignment_id = fields.Many2one('wk.grade.assignment', string='Assignment', domain="[('state','=','approve')]")
    class_assignment_id = fields.Many2one(
        'wk.class.assignment', string='Class Assignment')
    populate_class_id = fields.Many2one(
        'wk.school.class', related="class_assignment_id.class_id", store=True)
    exempted = fields.Boolean(string='Exempted')
    total_marks = fields.Integer(string="Total Marks", required=True)
    marks_obtained = fields.Float(string="Marks Obtained")
    percent_obtained = fields.Float(string="(%) Obtained")
    point_obtained = fields.Integer(string="Points")
    description = fields.Text(string='Remarks')
    scale_line_id = fields.Many2one(
        'wk.grade.scale.line', string="Symbol", domain="[('id', 'in',scale_line_id_domain)]")
    scale_line_id_domain = fields.Many2many(
        'wk.grade.scale.line', compute='_get_scale_line_id')
    submitted_assignment_attachment = fields.Binary(string="Attachment")
    submit_attachment_type = fields.Selection([('image', 'Image'),
                                               ('pdf', 'PDF'), ('doc', 'DOC'), ('zip', 'ZIP'),], string='Attachment Type')
    filename = fields.Char()
    submit_comment = fields.Text(string="Comment")
    assignment_description = fields.Html(
        string='Description', related='assignment_id.description', store=True)
    attachment_ids = fields.Many2many('wk.assignment.attachment', string="Attachments",
                                      readonly=True, related='class_assignment_id.attachment_ids')
    type_id = fields.Many2one('wk.assignment.type',
                              related='assignment_id.type_id', store=True)
    term_id = fields.Many2one(
        'wk.grade.terms', string="Term", related='populate_class_id.term_id', store=True)

    @api.depends('student_subject_id')
    def _compute_display_name(self):
        for student in self:
            student.display_name = student.student_id.name

    def mark_submitted(self):
        for obj in self:
            if obj.state != 'new':
                raise UserError(
                    _("Only new assignments can be marked as submitted."))
            obj.state = 'submit'
        return True

    def mark_checked(self):
        for obj in self:
            if obj.state != 'submit':
                raise UserError(
                    _("Only submitted assignments can be marked as checked."))
            obj.state = 'evaluate'
        return True

    @api.depends('class_assignment_id')
    def _get_student_subject_id(self):
        for record in self:
            if record.class_assignment_id:
                record.student_subject_id_domain = record.populate_class_id.student_ids
            else:
                record.student_subject_id_domain = False

    @api.depends('subject_id')
    def _get_scale_line_id(self):
        for record in self:
            if record.subject_id:
                scale_id = record.subject_id.scale_id
                record.scale_line_id_domain = scale_id.scale_line_ids
            else:
                record.scale_line_id_domain = False

    @api.onchange('marks_obtained')
    def onchange_marks_obtained(self):
        if self.marks_obtained > self.total_marks:
            raise ValidationError(
                _('Marks obtained cannot be greater than Total Marks.'))

        if self.marks_obtained and not self.env.context.get('evaluate'):
            percent_obtained = (self.marks_obtained / self.total_marks) * 100
            scale_id = self.subject_id.scale_id

            scale_line = self.env['wk.grade.scale.line'].search([
                ('min_percent', '<=', percent_obtained),
                ('max_percent', '>=', percent_obtained),
                ('scale_id', '=', scale_id.id)])

            point_obtained = scale_line.points

            self.with_context(evaluate=1).write({
                'percent_obtained': percent_obtained,
                'point_obtained': point_obtained,
                'scale_line_id': scale_line.id,
            })

    def submit_assignment_action(self):
        assignment = self.mapped('class_assignment_id')
        if len(assignment) > 1:
            raise ValidationError(
                _('Only same assignments can be submitted at once.'))
        evaluated_assignments = []
        result = ""
        for record in self:
            if record.state == 'evaluate':
                evaluated_assignments.append(record.student_id.name)
                result = ", ".join(evaluated_assignments)

        if len(result) > 0:
            raise ValidationError(
                _(f'The assignment {record.assignment_id.name} is already evaluated for {result} .You cannot submit it again.'))

        action = {
            'type': 'ir.actions.act_window',
            'name': _('Assignment Submission'),
            'view_mode': 'form',
            'res_model': 'wk.evaluation.wizard',
            'target': 'new',
            'views': [(self.env.ref('wk_school_management.wk_evaluation_wizard_submit_form').id, 'form'), (False, "list")],
            'context': {
                    'default_assignment_id': self[0].assignment_id.id,
                    'default_grade_id': self[0].grade_id.id,
                    'default_section_id': self[0].section_id.id,
                    'default_subject_id': self[0].subject_id.id,
                    'default_start_date': self[0].start_date,
                    'default_end_date': self[0].end_date,
                    'default_scale_id': self[0].subject_id.scale_id.id,
                    'default_total_marks': self[0].total_marks,
                    'default_student_assignment_ids': self.ids,
            }
        }
        return action

    def evaluate_assignment_action(self):
        assignment = self.mapped('class_assignment_id')
        if len(assignment) > 1:
            raise ValidationError(_('Only same assignments can be evaluated.'))

        action = self.env["ir.actions.act_window"]._for_xml_id(
            "wk_school_management.wk_evaluation_wizard_action")
        action['context'] = {
            'default_assignment_id': self[0].assignment_id.id,
            'default_grade_id': self[0].grade_id.id,
            'default_section_id': self[0].section_id.id,
            'default_subject_id': self[0].subject_id.id,
            'default_start_date': self[0].start_date,
            'default_end_date': self[0].end_date,
            'default_scale_id': self[0].subject_id.scale_id.id,
            'default_total_marks': self[0].total_marks,
            'default_student_assignment_ids': self.ids,
        }
        return action

    def get_gradesheet_record(self, populate_class, student):
        assignments = self.search(
            [('populate_class_id', '=', populate_class.id), ('student_subject_id', '=', student.id)])
        scores = {}

        for assignment in assignments:
            type_id = assignment.type_id.id
            if type_id not in scores:
                scores[type_id] = {'total': 0.0, 'count': 0}

            scores[type_id]['total'] += assignment.percent_obtained
            scores[type_id]['count'] += 1

        student_result = []
        avg_score = []
        initial = 0
        for type_id, data in scores.items():
            if data['count'] > 0:
                average = data['total'] / data['count']
            else:
                average = 0
            type_name = self.env['wk.assignment.type'].browse(type_id)
            result = (type_name.name, round(average, 2))
            assignment_type = self.env['wk.class.assignment.type'].search(
                [('assignment_type_id', '=', type_id), ('populate_class_id', '=', populate_class.id)])
            weightage = assignment_type.weightage
            assign_average = (average) * (weightage / 100)
            initial += assign_average

            student_result.append(result)
            avg_score.append(initial)
        return student_result, avg_score

    @api.onchange('submit_attachment_type', 'submitted_assignment_attachment')
    def _onchange_submit_student_assignment(self):
        mime_type_mapping = {
            'image': 'image',
            'pdf': 'application/pdf',
            'zip': 'application/zip',
            'doc': 'application/msword',
        }

        for assignment in self:
            if assignment.submit_attachment_type and assignment.submitted_assignment_attachment:
                decoded_file = base64.b64decode(
                    assignment.submitted_assignment_attachment)

                mime_type = guess_mimetype(decoded_file)
                expected_mime_type = mime_type_mapping.get(
                    assignment.submit_attachment_type)

                if not mime_type.startswith(expected_mime_type):
                    raise UserError(
                        f'Invalid file type. Expected a file of type {assignment.submit_attachment_type}.')

    def submit_assignment_button(self):
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Assignment Submission'),
            'view_mode': 'form',
            'res_model': 'wk.evaluation.wizard',
            'target': 'new',
            'views': [(self.env.ref('wk_school_management.wk_evaluation_wizard_submit_form').id, 'form'), (False, "list")],
            'context': {
                'default_assignment_id': self.assignment_id.id,
                'default_grade_id': self.grade_id.id,
                'default_section_id': self.section_id.id,
                'default_subject_id': self.subject_id.id,
                'default_start_date': self.start_date,
                'default_end_date': self.end_date,
                'default_scale_id': self.subject_id.scale_id.id,
                'default_total_marks': self.total_marks,
                'default_student_assignment_ids': self.ids,
            }
        }
        return action
