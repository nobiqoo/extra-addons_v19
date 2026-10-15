# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from random import randint

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class AttendanceTag(models.Model):
    _name = 'wk.attendance.tag'
    _description = 'Attendance Tags'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string='Name', required=True)
    color = fields.Integer('Color', default=_get_default_color)
    sequence = fields.Integer(default=1)
    description = fields.Text(string='Description')

    @api.constrains('name')
    def check_for_unique_attendance_tag(self):
        for record in self:
            tag = self.search([
                ('name', 'ilike', record.name),
                ('id', '!=', record.id)])

            if tag:
                raise UserError(
                    _(f"The Attendance Tag '{record.name}' already exists."))


class StudentClassAttendance(models.Model):
    _name = 'wk.student.class.attendance'
    _inherit = "wk.company.visibility.mixin"
    _description = 'Student Class wise Attendance'
    _rec_name = 'student_id'
    _order = 'class_date desc'

    student_id = fields.Many2one(
        'student.student', string=" Student", required=True)
    class_id = fields.Many2one(
        'wk.class.timetable', string="Class", domain="[('id','in',class_ids_domain)]")
    class_ids_domain = fields.Many2many(
        'wk.class.timetable', string='Class Domain', compute='get_class_id_domain')
    state = fields.Selection(
        [('present', 'Present'), ('absent', 'Absent')], string='Status', required=True)
    attendance_tag_ids = fields.Many2many('wk.attendance.tag', string="Tags")
    class_date = fields.Date(
        string="Class Date", default=fields.Date.context_today)
    student_attendance_id = fields.Many2one(
        'wk.student.attendance', 'Student Attendance', ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            student_attendance = self.env['wk.student.attendance'].search([
                ('student_id', '=', record.student_id.id),
                ('attendance_date', '=', record.class_date),
                ('company_id', '=', record.company_id.id)])
            if not student_attendance:
                student_attendance = self.env['wk.student.attendance'].create({
                    'student_id': record.student_id.id,
                    'attendance_date': record.class_date,
                    'company_id': record.company_id.id,
                    'attendance_state': record.state,
                })
            else:
                if student_attendance.attendance_state == 'absent' and record.state == 'present':
                    student_attendance.write({'attendance_state': 'present'})
            record.student_attendance_id = student_attendance.id
        return records

    @api.depends('student_id', 'class_date')
    def get_class_id_domain(self):
        for record in self:
            if record.student_id and record.class_date:
                class_ids = self.env['wk.class.timetable'].search(
                    [('class_date', '=', record.class_date)])
                classes = class_ids.filtered(
                    lambda m: record.student_id.id in m.student_ids.student_id.ids)
                record.class_ids_domain = classes
            else:
                record.class_ids_domain = False

    @api.constrains('class_date', 'student_id', 'class_id')
    def _unique_attendance_date_wise(self):
        for record in self:
            attendance = self.search([
                ('class_date', '=', record.class_date),
                ('student_id', '=', record.student_id.id),
                ('class_id', '=', record.class_id.id),
                ('id', '!=', record.id)])

            if attendance:
                raise ValidationError(
                    _(f"The attendance for {record.student_id.name} already exists for date {record.class_date} in class {record.class_id.name}."))
