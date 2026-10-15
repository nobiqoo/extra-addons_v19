# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, Command, _
import logging
_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):

    _inherit = "hr.employee"

    is_teacher = fields.Boolean(string="Is a teacher ?", groups="base.group_system,hr.group_hr_user,wk_school_management.wk_school_management_staff_group,wk_school_management.group_librarian_group")
    is_supervisor = fields.Boolean(string="Is a supervisor?", groups="wk_school_management.wk_school_management_staff_group")
    is_librarian = fields.Boolean(string="Is a Librarian ?", groups="base.group_user")
    current_leave_id = fields.Many2one('hr.leave.type', compute='_compute_current_leave', string="Current Time Off Type",
                                       groups="base.group_user")
    message_main_attachment_id = fields.Many2one(groups="base.group_user")
    subject_ids = fields.Many2many('wk.grade.subjects', string="Subjects")
    last_check_in = fields.Datetime(groups="base.group_user")
    activity_ids = fields.One2many(groups="base.group_user")
    activity_state = fields.Selection(groups="base.group_user")
    activity_user_id = fields.Many2one(groups="base.group_user")
    activity_type_id = fields.Many2one(groups="base.group_user")
    activity_type_icon = fields.Char(groups="base.group_user")
    activity_date_deadline = fields.Date(groups="base.group_user")
    my_activity_date_deadline = fields.Date(groups="base.group_user")
    activity_summary = fields.Char(groups="base.group_user")
    activity_exception_decoration = fields.Selection(groups="base.group_user")
    activity_exception_icon = fields.Char(groups="base.group_user")
    attendance_manager_id = fields.Many2one(groups="base.group_user")
    version_id = fields.Many2one(groups="base.group_user")
    message_ids = fields.One2many(groups="base.group_user")
    message_partner_ids = fields.Many2many(groups="base.group_user")
    message_is_follower = fields.Boolean(groups="base.group_user")
    message_follower_ids = fields.One2many(groups="base.group_user")
    work_location_name = fields.Char("Work Location Name", compute_sudo=True, compute="_compute_work_location_name")
    work_location_type = fields.Selection([
        ("home", "Home"),
        ("office", "Office"),
        ("other", "Other")], compute_sudo=True, compute="_compute_work_location_type", tracking=True)

    def _compute_current_leave(self):
        today = fields.Date.context_today(self)
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', self.ids),
            ('date_start', '<=', today),
            ('date_end', '>=', today),
            ('state', 'in', ['validated', 'paid']),
        ], order='date_start desc')
        leaves_by_employee = {}
        for leave in leaves:
            leaves_by_employee.setdefault(leave.employee_id.id, leave)
        for employee in self:
            leave = leaves_by_employee.get(employee.id)
            employee.current_leave_id = leave.leave_type_id if leave else False
    
    def grant_librarian_access(self):
        for rec in self:
            librarian_group = self.env.ref('wk_school_management.group_librarian_group')
            if rec.user_id:
                rec.is_librarian = True
                rec.user_id.write({
                    'group_ids': [(4, librarian_group.id)]
                })
        message = "Education Librarian Access has been approved."
        return {
            'type': 'ir.actions.act_window',
            'name': 'Message',
            'res_model': 'wk.message.wizard',
            'views': [(self.env.ref('wk_school_management.wk_message_wizard_view_form_success').id, 'form')],
            'target': 'new',
            'context': {
                'default_message': message
            }
        }

    def action_create_user(self):
        self.ensure_one()
        res = super().action_create_user()
        if res.get('context', False).get('default_is_teacher', False):
            res.get('context', False)['default_group_ids'] = [
                Command.link(self.env.ref('base.group_user').id),
                Command.link(self.env.ref(
                    'wk_school_management.group_school_leave_responsible').id),
                Command.link(self.env.ref(
                    'hr_attendance.group_hr_attendance_officer').id),
                Command.link(self.env.ref(
                    'hr_attendance.group_hr_attendance_own_reader').id),
                Command.link(self.env.ref(
                    'wk_school_management.wk_school_management_staff_group').id),
            ]
            
        if res.get('context', False).get('default_is_librarian', False):
            res.get('context', False)['default_group_ids'] = [
                Command.link(self.env.ref('base.group_user').id),
                Command.link(self.env.ref(
                    'wk_school_management.group_school_leave_responsible').id),
                Command.link(self.env.ref(
                    'hr_attendance.group_hr_attendance_own_reader').id),
                Command.link(self.env.ref(
                    'wk_school_management.group_librarian_group').id),
            ]
        return res

    def action_teacher_access(self):
        self.ensure_one()
        user = self.user_id.sudo()
        staff_group = self.env.ref(
            'wk_school_management.wk_school_management_staff_group'
        )
        if not user.has_group('wk_school_management.wk_school_management_staff_group'):
            user.group_ids = [(4, staff_group.id)]

        self.is_teacher = True
        message = (_("Teacher access has been granted"))
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Teacher Access',
            'res_model': 'wk.message.wizard',
            'views': [(self.env.ref('wk_school_management.wk_message_wizard_view_form_success').id, 'form')],
            'target': 'new',
            'context': {
                'default_message': message
            }
        }
        return action
