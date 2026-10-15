# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from markupsafe import Markup
import logging
import pytz

_logger = logging.getLogger(__name__)


class TimetableConfirmWizard(models.TransientModel):

    _name = 'wk.confirm.timetable'
    _inherit = 'wk.section.visibility.mixin'
    _description = 'A confirmation wizard for weekly slots'

    name = fields.Char(string='Title', readonly=True)
    weekly_schedule_ids = fields.Many2many(
        'wk.weekly.schedule', string="Weekly Schedule", readonly=True)
    grade_id = fields.Many2one(
        "wk.school.grade", string="Grade", readonly=True)
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", readonly=True)
    start_date = fields.Date(string="Start From", readonly=True)
    end_date = fields.Date(string="End Till", readonly=True)
    subject_id = fields.Many2one(
        'wk.grade.subjects', string='Subject', readonly=True)

    def schedule_now(self):
        populate_class_id = self.env.context.get('active_id')
        populate_class = self.env['wk.school.class'].browse(populate_class_id)

        start_date = populate_class.start_date
        end_date = populate_class.end_date

        new_schedule = populate_class.weekly_schedule_ids.filtered(
            lambda e: e.state == 'new')
        if not new_schedule:
            raise UserError(_("Classes already scheduled."))

        user_tz = pytz.timezone(self.env.user.tz or 'UTC')

        for schedule in populate_class.weekly_schedule_ids:
            current_date = start_date

            while current_date <= end_date:
                if schedule.state == 'new' and \
                schedule.weekday.capitalize() == current_date.strftime("%A"):

                    start_str, end_str = schedule.timeslot_id.name.split('-')

                    start_time_str = f'{current_date} {start_str}'
                    end_time_str = f'{current_date} {end_str}'

                    start_time_local = datetime.strptime(
                        start_time_str, '%Y-%m-%d %I:%M %p'
                    )

                    end_time_local = datetime.strptime(
                        end_time_str, '%Y-%m-%d %I:%M %p'
                    )
                    start_time_user_tz = user_tz.localize(start_time_local)
                    end_time_user_tz = user_tz.localize(end_time_local)

                    start_time_utc = start_time_user_tz.astimezone(pytz.UTC).replace(tzinfo=None)
                    end_time_utc = end_time_user_tz.astimezone(pytz.UTC).replace(tzinfo=None)

                    subject = populate_class.subject_id
                    grade = populate_class.grade_id
                    name = (
                        f"{grade.name}{populate_class.title}-"
                        f"{subject.name}({current_date})"
                    )

                    self.env['wk.class.timetable'].create({
                        'name': name,
                        'grade_id': populate_class.grade_id.id,
                        'subject_id': populate_class.subject_id.id,
                        'location_id': schedule.location_id.id,
                        'timeslot_id': schedule.timeslot_id.id,
                        'session_id': populate_class.session_id.id,
                        'term_id': populate_class.term_id.id,
                        'class_date': current_date,
                        'day': schedule.weekday,
                        'teacher_id': populate_class.teacher_id.id,
                        'populate_class_id': populate_class.id,
                        'start_time': start_time_utc,
                        'end_time': end_time_utc,
                    })

                current_date += timedelta(days=1)
            schedule.state = 'done'


class TimetablePostponeWizard(models.TransientModel):
    _name = 'wk.timetable.postpone.wizard'
    _description = 'Postpone Class Wizard'

    timetable_id = fields.Many2one(
        'wk.class.timetable', required=True, readonly=True)
    class_date = fields.Date(string='New Date', required=True)
    timeslot_id = fields.Many2one('wk.class.timeslot', string='New Time', required=True)
    location_id = fields.Many2one('wk.class.location', string='New Location', required=True)
    reason = fields.Text(string='Reason', required=True)

    def action_postpone(self):
        self.ensure_one()
        timetable = self.timetable_id

        old_vals = {
            'date': timetable.class_date,
            'day': timetable.day,
            'timeslot': timetable.timeslot_id.name,
            'location': timetable.location_id.name,
        }
        new_day = self.class_date.strftime('%A').lower()

        timetable._check_location_availability(
            self.class_date,
            new_day,
            self.timeslot_id,
            self.location_id
        )

        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        start_str, end_str = self.timeslot_id.name.split('-')
        start_time_str = f'{self.class_date} {start_str}'
        end_time_str = f'{self.class_date} {end_str}'

        start_time_local = datetime.strptime(
            start_time_str, '%Y-%m-%d %I:%M %p')
        end_time_local = datetime.strptime(
            end_time_str, '%Y-%m-%d %I:%M %p')

        start_time_user_tz = user_tz.localize(start_time_local)
        end_time_user_tz = user_tz.localize(end_time_local)

        start_time_utc = start_time_user_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        end_time_utc = end_time_user_tz.astimezone(pytz.UTC).replace(tzinfo=None)

        new_name = timetable._compute_display_name_with_date(self.class_date)
        timetable.write({
            'name': new_name,
            'class_date': self.class_date,
            'day': new_day,
            'timeslot_id': self.timeslot_id.id,
            'location_id': self.location_id.id,
            'start_time': start_time_utc,
            'end_time': end_time_utc,
        })

        message = Markup(
            _(
                "<div style='line-height:1.6;'>"
                "<b>Class Postponed By:</b> %s<br/><br/>"

                "<b>Previous Schedule</b>"
                "<ul>"
                "<li><b>Date: <span style='color:#d9534f;'>%s (%s)</span></b></li>"
                "<li><b>Time:</b> %s</li>"
                "<li><b>Location:</b> %s</li>"
                "</ul>"

                "<b>New Schedule</b>"
                "<ul>"
                "<li><b>Date: <span style='color:#5cb85c;'>%s (%s)</span></b></li>"
                "<li><b>Time:</b> %s</li>"
                "<li><b>Location:</b> %s</li>"
                "</ul>"

                "<b>Reason</b><br/>"
                "<div style='margin-left:16px;'>%s</div>"
                "</div>"
            ) % (
                self.env.user.name,
                old_vals['date'],
                old_vals['day'].capitalize(),
                old_vals['timeslot'],
                old_vals['location'],
                self.class_date,
                new_day.capitalize(),
                self.timeslot_id.name,
                self.location_id.name,
                self.reason or '-',
            )
        )

        timetable.message_post(body=message)
