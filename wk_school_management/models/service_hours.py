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
from datetime import timedelta

import logging

_logger = logging.getLogger(__name__)


class ServiceHours(models.Model):
    _name = 'wk.service.hours'
    _description = 'Student Service Hours'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'wk.company.visibility.mixin']
    _order = "create_date desc"

    name = fields.Char(string='Title', required=True)
    state = fields.Selection([('new', 'New'),
                              ('approve', 'Approved'),
                              ('reject', 'Rejected')], string="Status", default='new')
    start_time = fields.Datetime(string="Start Time", required=True)
    end_time = fields.Datetime(string="End Time", compute='_compute_end_time')
    total_hours = fields.Float(required=True, string='Total Hours')
    comment = fields.Text(string='Comment')
    student_id = fields.Many2one(
        'student.student', string="Student ", required=True)
    supervisor_id = fields.Many2one(
        'hr.employee', domain=[('is_supervisor', '=', True)], required=True)
    approver_id = fields.Many2one('hr.employee', string="Approved By")
    enrollment_id = fields.Many2one(
        'student.enrollment', string="Enrollment", compute='_compute_student_enrollment', store=True)
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)

    @api.constrains('total_hours')
    def check_total_hours(self):
        for hours in self:
            if hours.total_hours == 0.0:
                raise ValidationError(
                    _('Service Hours should be greater then 0.'))
            if hours.total_hours > 24:
                raise ValidationError(_('Time cannot exceed 24 hours.'))

    @api.depends('start_time', 'total_hours')
    def _compute_end_time(self):
        for hours in self:
            if hours.start_time and hours.total_hours:
                time = hours.start_time + timedelta(hours=hours.total_hours)
                hours.end_time = time
            else:
                hours.end_time = False

    def approve_service_hour(self):
        for hours in self:
            if hours.state != 'new':
                raise UserError(
                    _("Only new service hours can be marked as approved."))
            approver = self.env.user
            hours.approver_id = approver.employee_id
            hours.state = 'approve'

    def reject_service_hour(self):
        for hours in self:
            if hours.state != 'new':
                raise UserError(
                    _("Only new service hours can be marked as rejected."))
            hours.state = 'reject'

    @api.depends('student_id')
    def _compute_student_enrollment(self):
        for hours in self:
            if hours.student_id:
                enrollment = self.env['student.enrollment'].search(
                    [('student_id', '=', hours.student_id.id), ('state', '=', 'progress')], limit=1)
                hours.enrollment_id = enrollment
            else:
                hours.enrollment_id = False
