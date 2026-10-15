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
import re

_logger = logging.getLogger(__name__)


class WkApplicationForm(models.Model):

    _name = "wk.application.form"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'wk.company.visibility.mixin']
    _description = "Application Management"
    _order = "create_date desc"

    name = fields.Char(
        string="Application Reference",
        required=True, default=lambda self: _('New'))
    student_name = fields.Char(string="Student Name", required=True)
    application_date = fields.Date(
        string="Recieved on", default=fields.Date.context_today)
    student_image = fields.Image('Image', required=True, attachment=False)
    dob = fields.Date(string="Date of Birth")
    mother_name = fields.Char(string="Mother's Name")
    father_name = fields.Char(string="Father's Name")
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street2")
    zip = fields.Char(change_default=True, string="ZIP")
    city = fields.Char(string="City")
    state_id = fields.Many2one("res.country.state", string='State',
                               ondelete='restrict', domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one(
        'res.country', string='Country', ondelete='restrict')
    country_code = fields.Char(
        related='country_id.code', string="Country Code")
    email = fields.Char(string="Email", required=True)
    phone = fields.Char(string="Phone", required=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female'), (
        'other', 'Other')], default="male", string="Gender", required=True)
    state = fields.Selection([
        ('new', 'New'),
        ('confirm', 'Confirmed'),
        ('enroll', 'Enrolled'),
        ('cancel', 'Cancelled')
    ], string='Application Status', default="new", readonly=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    grade_id = fields.Many2one(
        "wk.school.grade", string="Grade", required=True)
    student_id = fields.Many2one('student.student', 'Student')
    queries = fields.Text(string="Queries")
    blood_group = fields.Selection([('a+', "A+"), ('a-', "A-"), ('b+', "B+"), ('b-', "B-"),
        ('ab+', "AB+"), ('ab-', "AB-"), ('o+', "O+"), ('o-', "O-")], string="Blood group")
    medical_disability = fields.Selection([('yes',"Yes"),('no',"No")],
            default="no", string="Any identified disability/ailment?")
    known_medical_disability = fields.Text(string="Known Medical Illness/Condition/Disability")
    mothers_contact = fields.Char(string="Mother's Contact Number")
    fathers_contact = fields.Char(string="Father's Contact Number")
    mothers_occupation = fields.Char(string="Mother's Occupation")
    fathers_occupation = fields.Char(string="Father's Occupation")
    parent_email = fields.Char(string="Parent Email")
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'wk_application_attachment_rel',
        'application_id',
        'attachment_id',
        string='Documents'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'application.form.sequence') or _("New")
        application_ids = super().create(vals_list)
        if not self.env.context.get('install_mode'):
            for application in application_ids:
                mail_template = self.env.ref('wk_school_management.application_submission_mail', raise_if_not_found=False)
                if mail_template:
                    mail_template.sudo().send_mail(application.id, force_send=True)
        return application_ids

    @api.constrains('dob')
    def check_for_dob(self):
        for application in self:
            if application.dob and application.dob > fields.Date.today():
                raise ValidationError(
                    _("Date of Birth cannot be greater than today's date."))

    @api.constrains('email', 'grade_id')
    def check_for_unique_application(self):
        for application in self:
            record = self.search([
                ('email', '=', application.email),
                ('grade_id', '=', application.grade_id.id),
                ('id', '!=', application.id)])
            if record:
                raise ValidationError(
                    _(f"Application for {application.name} already exists in grade {application.grade_id.name}!\n Please enter any other email id."))

    @api.constrains('email')
    def _check_email_format(self):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        for record in self:
            if record.email:
                if not re.match(email_regex, record.email):
                    raise ValidationError(
                        "The email address is not valid. Please enter a valid email.")

    @api.constrains('phone')
    def _check_phone_number(self):
        for record in self:
            if not re.fullmatch(r'\d+', record.phone or ''):
                raise ValidationError("Phone number must contain only digits.")

    def confirm_application(self):
        for obj in self:
            if obj.state != 'new':
                raise UserError(
                    _("Only new application can be marked as confirmed."))
            obj.state = 'confirm'
            mail_template = self.env.ref('wk_school_management.application_confirmation_mail', raise_if_not_found=False)
            if mail_template:
                mail_template.send_mail(obj.id, force_send=True)
        return True

    def enroll_application(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "wk_school_management.enroll_wizard_action")
        student = self.env['student.student'].search(
            [('application_id', '=', self.id)])
        if student:
            action['context'] = {
                'default_student_id': student.id
            }
        return action

    def get_student_id(self):
        self.ensure_one()
        student_id = self.env['student.student'].search([('application_id', '=', self.id)])
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'form',
            'res_id': student_id.id,
            'views': [[self.env.ref('wk_school_management.student_student_form').id, 'form']],
        }
