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


class AssignmentType(models.Model):

    _name = 'wk.assignment.type'
    _description = 'Assignment Type'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(default=1)

    @api.constrains('name')
    def check_for_unique_assignment_type(self):
        for record in self:
            type = self.search([
                ('name', 'ilike', record.name),
                ('id', '!=', record.id)])

            if type:
                raise UserError(
                    _(f"The assignment type {record.name} already exists."))


class GradeAssignment(models.Model):

    _name = 'wk.grade.assignment'
    _inherit = "wk.company.visibility.mixin"
    _description = 'Grade Assignment'
    _order = "create_date desc"

    name = fields.Char(string='Name', required=True)
    state = fields.Selection([('draft', 'Draft'), ('approve', 'Approved')],
                             string="Status", default="draft")
    grade_id = fields.Many2one(
        "wk.school.grade", string='Grade', required=True, domain="[('id', 'in', grade_id_domain )]")
    grade_id_domain = fields.Many2many(
        'wk.school.grade', compute='_get_default_grade_domain')
    teacher_id = fields.Many2one("hr.employee", string='Teacher', required=True, domain="[('is_teacher','=',True),('subject_ids','=',subject_id)]",
                                 default=lambda self: self.env.user.employee_id.id if self.env.user.employee_id.id and self.env.user.employee_id.is_teacher else None)
    subject_id = fields.Many2one("wk.grade.subjects", string='Subject',
                                 required=True, domain="[('grade_id', '=', grade_id)]")
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    type_id = fields.Many2one("wk.assignment.type",
                              string='Assignment Type', required=True)
    description = fields.Html(string='Description')
    attachment_ids = fields.One2many(
        'wk.assignment.attachment', 'assignment_id', string="Attachments")
    class_assignment_count = fields.Integer(string="Assignments", compute='_compute_class_assignment_count')

    def approve_assignment(self):
        for obj in self:
            obj.state = 'approve'
        return True

    def write(self, vals):
        res = super().write(vals)
        if 'attachment_ids' in vals:
            assignments = self.env['wk.class.assignment'].search(
                [('assignment_id', '=', self.id)])
            for assignment in assignments:
                assignment.attachment_ids = ([(6, 0, self.attachment_ids.ids)])
        return res

    @api.onchange('grade_id')
    def _onchange_grade_id(self):
        self.subject_id = False
        self.teacher_id = False

    @api.depends('teacher_id')
    def _get_default_grade_domain(self):
        for plans in self:
            if self.env.user.has_group('wk_school_management.wk_school_management_staff_group') and not self.env.user.has_group('wk_school_management.wk_school_management_officer_group'):
                grades = []
                for grade_id in self.env.user.employee_id.subject_ids.grade_id:
                    grade = self.env['wk.school.grade'].search([('id', '=', grade_id.id)])
                    grades.append(grade.id)
                plans.grade_id_domain = grades
            else:
                plans.grade_id_domain = self.env['wk.school.grade'].search([])

    def _compute_class_assignment_count(self):
        for obj in self:
            obj.class_assignment_count = self.env['wk.class.assignment'].search_count(
                [('assignment_id', '=', obj.id)])

    def get_assigned_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': ' Classes Scheduled',
            'res_model': 'wk.class.assignment',
            'view_mode': 'list,form',
            'domain': [('assignment_id.id', '=', self.id)]
        }
