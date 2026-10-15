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


class ClassTimeslot(models.Model):

    _name = 'wk.class.timeslot'
    _description = 'Class Timeslot'

    name = fields.Char('Timeslot', default=lambda self: _('New'))
    sequence = fields.Integer(default=1)
    start_time = fields.Float('Start Time', required=True)
    end_time = fields.Float('End Time', required=True)


    @api.model
    def float_to_time(self, float_time):
        if float_time < 0 or float_time >= 24:
            raise ValidationError(_("Time must be within 0-24 hours."))

        minutes = float_time * 60
        hours, minutes = divmod(minutes, 60)
        period = "AM"
        if hours >= 12:
            period = "PM"
            if hours > 12:
                hours -= 12
        if hours == 0:
            hours = 12

        time_string = "%02d:%02d  %s" % (hours, minutes, period)
        return time_string

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if 'start_time' in vals:
                    float_start_time = vals['start_time']
                    start = self.float_to_time(float_start_time)
                if 'end_time' in vals:
                    float_end_time = vals['end_time']
                    end = self.float_to_time(float_end_time)

                if float_start_time > float_end_time:
                    raise UserError(
                        (_('Error! The Duration of timeslot is invalid!')))

                vals['name'] = str(start) + '-' + str(end) or _('New')
        return super(ClassTimeslot, self).create(vals_list)

    def write(self, vals):

        if 'start_time' in vals and 'end_time' in vals:
            float_start_time = vals['start_time']
            float_end_time = vals['end_time']
            if float_start_time > float_end_time:
                raise UserError(
                    _('Error! The Duration of timeslot is invalid!'))

            start = self.float_to_time(float_start_time)
            end = self.float_to_time(float_end_time)
            vals['name'] = str(start) + '-' + str(end)

        elif 'start_time' in vals:
            float_start_time = vals['start_time']
            float_end_time = self.end_time

            if float_start_time > float_end_time:
                raise UserError(
                    _('Error! The Duration of timeslot is invalid!'))

            start = self.float_to_time(float_start_time)
            end = self.float_to_time(float_end_time)

            vals['name'] = str(start) + '-' + str(end)

        elif 'end_time' in vals:
            float_start_time = self.start_time
            float_end_time = vals['end_time']

            if float_start_time > float_end_time:
                raise UserError(
                    _('Error! The Duration of timeslot is invalid!'))

            start = self.float_to_time(float_start_time)
            end = self.float_to_time(float_end_time)

            vals['name'] = str(start) + '-' + str(end)

        return super().write(vals)
