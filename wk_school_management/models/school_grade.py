# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class WkGradeTerms(models.Model):

    _name = "wk.grade.terms"
    _description = "Gradewise Terms"

    name = fields.Char(string='Term', required=True)
    weightage = fields.Float(string='Weightage(%)')
    academic_year_id = fields.Many2one(
        'wk.academic.year', 'Academic Year', ondelete='cascade')
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)

    @api.onchange('start_date', 'end_date')
    def onchange_for_academic_year_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.start_date > record.end_date:
                    raise ValidationError(
                        _("Invalid duration.End date need to be after the start date."))

    @api.onchange('start_date', 'end_date', 'academic_year_id')
    def onchange_academic_date_with_session_date(self):
        for record in self:
            if record.start_date and record.end_date and record.academic_year_id.start_date and record.academic_year_id.end_date:
                if record.start_date < record.academic_year_id.start_date or record.end_date > record.academic_year_id.end_date:
                    raise ValidationError(
                        _("Term has to lie within Academic Year's duration."))

    @api.constrains('start_date', 'end_date')
    def _check_term_dates(self):
        for record in self:
            if record.start_date > record.end_date:
                raise ValidationError(
                    _("Invalid duration.End date need to be after the start date."))

            terms = self.search([
                ('academic_year_id', '=', record.academic_year_id.id),
                ('id', '!=', record.id),
                ('start_date', '<=', record.end_date),
                ('end_date', '>=', record.start_date)
            ])

            if terms:
                for term in terms:
                    if record.start_date < term.end_date:
                        raise ValidationError(
                            _(f"Term '{record.name}' start date must be after the end date of Term '{term.name}'."))


class SchoolGrade(models.Model):

    _name = "wk.school.grade"
    _inherit = "wk.company.visibility.mixin"
    _description = "Grade Details"
    _order = "write_date desc"

    name = fields.Char(string='Grade', required=True)
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    subject_ids = fields.One2many('wk.grade.subjects', 'grade_id', 'Subjects')
    teacher_ids = fields.Many2many(
        'hr.employee', 'Teachers', domain="[('is_teacher','=',True),('subject_ids','in',subject_ids)]", compute='_compute_grade_teachers')
    scale_id = fields.Many2one(
        'wk.grade.scales', string='Grade Scale', required=True)
    teacher_count = fields.Integer(
        string='Class Count', compute='_compute_teacher_count')
    section_ids = fields.One2many(
        'wk.grade.section', 'grade_id', string='Section', required=True)

    @api.constrains('name', 'company_id')
    def check_for_unique_grade(self):
        for grade in self:
            record = self.search([
                ('name', '=', grade.name),
                ('company_id', '=', grade.company_id.id),
                ('id', '!=', grade.id)])
            if record:
                raise ValidationError(
                    _(f"Grade {record.name} already exists!!"))
        return True

    @api.onchange('scale_id')
    def onchange_scale_subject_update(self):
        for record in self:
            for subject in record.subject_ids:
                if subject.optional_choice == False:
                    subject.scale_id = record.scale_id

    @api.depends('teacher_ids')
    def _compute_teacher_count(self):
        for record in self:
            if record.teacher_ids:
                record.teacher_count = len(record.teacher_ids)
            else:
                record.teacher_count = 0

    def get_grade_teachers(self):
        return {
            'type': 'ir.actions.act_window',
            'name': ' Teachers',
            'res_model': 'hr.employee',
            'views': [(self.env.ref('hr.hr_kanban_view_employees').id, 'kanban'), (False, "list"), (False, "form")],
            'domain': [('subject_ids', 'in', self.subject_ids.ids)]
        }

    @api.depends('subject_ids')
    def _compute_grade_teachers(self):
        for grade in self:
            if grade.subject_ids:
                teachers = self.env['hr.employee'].search(
                    [('is_teacher', '=', True), ('subject_ids', 'in', grade.subject_ids.ids)])
                grade.teacher_ids = teachers

            else:
                grade.teacher_ids = False


class SchoolSection(models.Model):

    _name = 'wk.grade.section'
    _inherit = "wk.company.visibility.mixin"
    _description = 'Grade Section'

    name = fields.Char(string='Section', required=True)
    grade_id = fields.Many2one(
        'wk.school.grade', string='Grade', required=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)   
    

class SectionVisibilityMixin(models.AbstractModel):
    _name = 'wk.section.visibility.mixin'
    _description = 'Section Visibility Mixin'

    section_visibility = fields.Boolean(compute='_compute_section_visibility', store=False)

    @api.depends('grade_id')
    def _compute_section_visibility(self):
        for record in self:
            record.section_visibility = bool(record.grade_id and record.grade_id.section_ids)
