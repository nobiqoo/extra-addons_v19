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
import logging

_logger = logging.getLogger(__name__)


class WeeklySchedule(models.Model):

    _name = 'wk.weekly.schedule'
    _description = 'Weekly schedule'

    DAYS = [('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'), ('friday',
                                       'Friday'), ('saturday', 'Saturday'),
            ('sunday', 'Sunday')]

    sequence = fields.Integer(default=1)
    state = fields.Selection(
        [('new', 'New'), ('done', 'Scheduled')], string="Status", default="new")
    weekday = fields.Selection(DAYS, string="Day", required=True)
    timeslot_id = fields.Many2one(
        'wk.class.timeslot', string="Period", required=True)
    location_id = fields.Many2one(
        'wk.class.location', string="Location", required=True)
    populate_class_id = fields.Many2one('wk.school.class', string="Class")

    @api.constrains('weekday', 'timeslot_id', 'location_id')
    def _check_timeslot_overlap(self):
        for record in self:
            overlapping_schedules = self.search([
                ('id', '!=', record.id),
                ('weekday', '=', record.weekday),
                ('location_id', '=', record.location_id.id),
                '|', '|',
                '&', ('timeslot_id.start_time', '<=',
                      record.timeslot_id.start_time),
                ('timeslot_id.end_time', '>', record.timeslot_id.start_time),
                '&', ('timeslot_id.start_time', '<',
                      record.timeslot_id.end_time),
                ('timeslot_id.end_time', '>=', record.timeslot_id.end_time),
                '&', ('timeslot_id.start_time', '>=',
                      record.timeslot_id.start_time),
                ('timeslot_id.end_time', '<=', record.timeslot_id.end_time)
            ])

            if overlapping_schedules:
                raise ValidationError(
                    _(f'{record.location_id.name} is already booked for the selected period on {record.weekday} at {record.timeslot_id.name}.'))

    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError(
                    _('A schedule already created cannot be deleted!!'))
        return super().unlink()
