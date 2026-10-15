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


class LessonPlan(models.Model):

    _name = 'wk.lesson.plan'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'wk.section.visibility.mixin', 'wk.company.visibility.mixin']
    _description = 'Lesson Plans'

    name = fields.Char(string='Title', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
        ('cancel', 'Cancelled')
    ], string='Status', default="draft", readonly=True, tracking=True)
    grade_id = fields.Many2one(
        'wk.school.grade', string='Grade', required=True, tracking=True, domain="[('id', 'in',grade_id_domain )]")
    grade_id_domain = fields.Many2many(
        'wk.school.grade', compute='_get_default_grade_domain')
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", domain="[('grade_id', '=', grade_id)]")
    subject_id = fields.Many2one('wk.grade.subjects', string='Subject',
                                 required=True, domain="[('grade_id','=',grade_id )]", tracking=True)
    responsible_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user.id, string="Prepared By")
    description = fields.Html(string='Lesson', required=True)
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    plan_visibility = fields.Selection([('all', 'All'),
                                        ('only_me', 'Only Me'),], string='Shared To', default="all")

    @api.onchange('grade_id')
    def onchange_grade_id(self):
        self.subject_id = False
        self.description = False

    def approve_lesson_plan(self):
        for obj in self:
            if obj.state != 'draft':
                raise UserError(_("Only new lesson plans can be approved."))
            obj.state = 'approve'

    def cancel_lesson_plan(self):
        for obj in self:
            if obj.state != 'draft':
                raise UserError(_("Only new lesson plans can be cancelled."))
            obj.state = 'cancel'

    def reset_lesson_plan(self):
        for obj in self:
            obj.state = 'draft'

    @api.depends('responsible_id')
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
