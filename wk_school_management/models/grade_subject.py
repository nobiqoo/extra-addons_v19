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


class WkGradeSubjects(models.Model):

    _name = "wk.grade.subjects"
    _inherit = ['wk.section.visibility.mixin', 'wk.company.visibility.mixin']
    _description = "Grade Subjects"
    _order = "sequence desc"

    name = fields.Char(string='Subject', required=True)
    sequence = fields.Integer(default=1)
    grade_id = fields.Many2one(
        'wk.school.grade', string='Grade', required=True)
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", domain="[('grade_id', '=', grade_id)]")
    lesson_plan_ids = fields.One2many(
        'wk.lesson.plan', 'subject_id', string='Lesson Plan', context={'from_grade_subject': True})
    optional_choice = fields.Boolean(string='Optional')
    scale_id = fields.Many2one('wk.grade.scales', string='Grade Scale')
    teacher_ids = fields.Many2many(
        'hr.employee', string="Teachers", domain="[('is_teacher','=',True)]")
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    credit_value = fields.Integer(string="Credit", required=True)
    subject_code = fields.Char(string="Code", required=True)

    @api.constrains('credit_value')
    def check_for_subject_credit(self):
        for subject in self:
            if subject.credit_value <= 0:
                raise UserError(_("Credit Value for the subject should be greater than 0."))

    @api.constrains('subject_code', 'grade_id')
    def check_for_unique_subject_code(self):
        for record in self:
            subject = self.search([
                ('grade_id', '=', record.grade_id.id),
                ('subject_code', 'ilike', record.subject_code),
                ('id', '!=', record.id)
            ])
            if subject:
                raise UserError(
                    _(f"Subject code '{record.subject_code}' for grade '{record.grade_id.name}' already exists!"))

    @api.onchange('optional_choice', 'grade_id')
    def onchange_optional_choice(self):
        if self.optional_choice:
            self.scale_id = False
        else:
            self.scale_id = self.grade_id.scale_id.id

    @api.constrains('name', 'grade_id')
    def check_for_unique_grade_subject(self):
        for record in self:
            subject = self.search([
                ('name', 'ilike', record.name),
                ('grade_id', '=', record.grade_id.id),
                ('id', '!=', record.id)])

            if subject:
                raise UserError(
                    _(f"The subject {record.name} already exists for grade {record.grade_id.name}."))

    @api.onchange('grade_id')
    def onchange_grade_id(self):
        if not self.grade_id:
            self.scale_id = False
        else:
            self.scale_id = self.grade_id.scale_id.id
