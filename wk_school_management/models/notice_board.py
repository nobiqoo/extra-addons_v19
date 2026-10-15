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


class NoticeBoard(models.Model):

    _name = 'wk.notice.board'
    _inherit = "wk.company.visibility.mixin"
    _description = 'Notice Board'
    _order = "create_date desc"

    name = fields.Char(string="Title", required=True)
    sequence = fields.Integer(default=1)
    description = fields.Html(string="Description", required=True)
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    visibility = fields.Selection([('all', 'All'),
                                   ('students', 'For Students'),
                                   ('teachers', 'For Teachers')], default="all", string="Visible To")
    state = fields.Selection([('active', 'Active'),
                              ('inactive', 'Archived')], string="Status", compute='_compute_notice_status', search='_search_active_notice')
    active = fields.Boolean(
        'Active', default=True,
        help="By unchecking the active field, you may hide a notice from notice board.")
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)

    @api.constrains('start_date', 'end_date')
    def _check_for_duration(self):
        for notice in self:
            if notice.start_date > notice.end_date:
                raise ValidationError(_
                                      ('Error! The duration of notice is invalid.'))
        return True

    @api.depends('start_date', 'end_date')
    def _compute_notice_status(self):
        for notice in self:
            if notice.start_date and notice.end_date:
                if notice.start_date > fields.Date.today():
                    notice.state = 'inactive'
                elif notice.start_date == fields.Date.today():
                    notice.state = 'active'
                elif notice.start_date < fields.Date.today() and notice.end_date >= fields.Date.today():
                    notice.state = 'active'
                elif notice.end_date < fields.Date.today():
                    notice.state = 'inactive'
            else:
                notice.state = False

    def _search_active_notice(self, operator, value):
        if operator == '=' and value == 'active':
            domain = [
                '|',
                ('start_date', '=', fields.Date.today()),
                '&',
                ('start_date', '<', fields.Date.today()),
                ('end_date', '>=', fields.Date.today()),
                '|',
                ('end_date', '>', fields.Date.today()),
                ('start_date', '>', fields.Date.today())
            ]
            notice_ids = self.search(domain)
            if notice_ids:
                return [('id', 'in', notice_ids.ids)]
            else:
                return [('id', '=', False)]
        return []
