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


class WkSchoolSession(models.Model):

    _name = "wk.school.session"
    _description = "School Session"
    _order = "create_date desc"

    name = fields.Char(string="Session", required=True)
    state = fields.Selection([('new', 'New'),
                              ('progress', 'In Progress'),
                              ('complete', 'Completed')], default='new', string='Status')
    start_date = fields.Date(string="Start From", required=True)
    end_date = fields.Date(string="End Till", required=True)
    enrollment_ids = fields.One2many(
        'student.enrollment', 'session_id', string='Enrollment')
    academic_year_ids = fields.One2many(
        'wk.academic.year', 'session_id', string='Academic Years')

    @api.constrains('end_date')
    def _check_for_duration(self):
        for period_obj in self:
            if period_obj.start_date > period_obj.end_date:
                raise UserError(
                    _('Error!\n The duration of the session is invalid'))
        return True

    def write(self, vals):
        res = super().write(vals)
        if vals.get('start_date') or vals.get('end_date'):
            if not self.env.context.get('install_mode'):
                if self.enrollment_ids:
                    raise UserError(
                        _('Date cannot be edited as SESSION is already linked to several ENROLLMENTS.'))
        return res

    def progress_session(self):
        for session in self:
            if session.state != 'new':
                raise UserError(_("Only new session can be started."))
            session.state = 'progress'
        return True

    def complete_session(self):
        for session in self:
            if session.state != 'progress':
                raise UserError(
                    _("Only In Progress session can be completed."))
            if session.end_date > fields.Date.today():
                raise UserError(_("Session's end date is yet to come."))
            session.state = 'complete'
        return True
