# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

import logging
import re
import base64
from random import choice
from string import digits
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from io import BytesIO
from PIL import Image
from reportlab.graphics import renderPM
from reportlab.graphics.barcode import createBarcodeDrawing

_logger = logging.getLogger(__name__)


class StudentDocumentType(models.Model):
    _name = 'wk.student.document.type'
    _description = 'Student Document Type'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(default=1)
    description = fields.Text(string='Description')


class StudentStudent(models.Model):

    _name = 'student.student'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'wk.company.visibility.mixin']
    _description = 'Student Details'
    _order = "create_date desc"
    _rec_name = "display_name"

    name = fields.Char(string="Student", required=True, tracking=True)
    display_name = fields.Char(compute="_compute_display_name", store=True, index=True)
    student_image = fields.Image('Image', required=True)
    parent_ids = fields.Many2many('res.partner', 'student_id', 'partner_id',
                            string='Guardians', domain="[('is_parent', '=', True)]")
    mother_name = fields.Char(string="Mother's Name", tracking=True)
    father_name = fields.Char(string="Father's Name", tracking=True)
    mothers_contact = fields.Char(string="Mother's Contact Number")
    fathers_contact = fields.Char(string="Father's Contact Number")
    mothers_occupation = fields.Char(string="Mother's Occupation")
    fathers_occupation = fields.Char(string="Father's Occupation")
    parent_email = fields.Char(string="Parent Email")
    company_id = fields.Many2one("res.company", string="School", default=lambda self: self.env.company, required=True)
    nationality_id = fields.Many2one('res.country', string="Nationality")
    gender = fields.Selection([('male', 'Male'), ('female', 'Female'), ('other', 'Other')], default="male", string="Gender")
    dob = fields.Date(string="Date of Birth", required=True)
    email = fields.Char(string="Email", tracking=True, required=True)
    mobile = fields.Char(string='Mobile', tracking=True, required=True)
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street2")
    zip = fields.Char(change_default=True, string="ZIP")
    city = fields.Char(string="City")
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict')
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    country_code = fields.Char(related='country_id.code', string="Country Code")
    user_id = fields.Many2one('res.users', string="User")
    attendance_ids = fields.One2many('wk.student.attendance', 'student_id', string='Attendance')
    enrollment_ids = fields.One2many('student.enrollment', 'student_id', string="Enrollment")
    application_id = fields.Many2one('wk.application.form', string="Application")
    current_enrollment_id = fields.Many2one('student.enrollment', string="Current Enrollment", compute='_compute_enrollment_grade_id',store=True)
    current_grade_id = fields.Many2one('wk.school.grade', string="Current Grade", compute='_compute_enrollment_grade_id', store=True)
    blood_group = fields.Selection([('a+', "A+"), ('a-', "A-"), ('b+', "B+"), ('b-', "B-"), ('ab+', "AB+"), ('ab-', "AB-"), ('o+', "O+"), ('o-', "O-")], string="Blood group")
    allergic_food = fields.Text(string="Allergic Food")
    allergic_medicine = fields.Text(string="Allergic Medicine")
    known_illness = fields.Text(string="Known Medical Illness/Condition")
    barcode = fields.Char(string="Student ID", help="ID used for student identification.", copy=False)
    partner_id = fields.Many2one('res.partner', string="Partner", copy=False)
    no_enrollments = fields.Boolean(string="Enrollments", compute='_compute_no_enrollments')
    student_active = fields.Boolean(string="Student Active", related='user_id.active')
    active = fields.Boolean('Active', default=True,
        help="By unchecking the active field, you may hide an inactive student.")
    parent_portal_active = fields.Boolean(string='Parent Portal Active', compute='_compute_parent_portal_active', store=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments',
        help="Attachments related to the student, such as documents or files.")
    
    is_transport_enabled = fields.Boolean(string="Transport Enabled", default=False, help="Indicates if the student is enabled for transport services.")
    route_id = fields.Many2one('transport.route', string='Transport Route', help="The transport route assigned to the student.")
    location_id = fields.Many2one('transport.location', string='Transport Location', help="The transport location associated with the student.")
    vertical_barcode_image = fields.Binary("Vertical Barcode Image", compute="_compute_vertical_barcode", store=True)
    library_fine_ids = fields.One2many('book.library.fine', 'student_id', string='Fine',)

    _SYNC_FIELD_MAP = {
        'name': 'name',
        'email': 'email',
        'mobile': 'phone',
        'street': 'street',
        'street2': 'street2',
        'zip': 'zip',
        'city': 'city',
        'state_id': 'state_id',
        'country_id': 'country_id',
        'student_image': 'image_1920',
    }

    @api.depends('barcode', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.barcode}] {rec.name}" if rec.barcode else rec.name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|',
                ('display_name', operator, name),
                ('name', operator, name),
                ('barcode', operator, name),
            ]
        students = self.search(domain + args, limit=limit)
        return [(student.id, student.display_name or student.name or "") for student in students]

    def _prepare_related_partner_vals(self):
        self.ensure_one()
        return {
            'name': self.name,
            'email': self.email,
            'phone': self.mobile,
            'street': self.street or False,
            'street2': self.street2 or False,
            'zip': self.zip or False,
            'city': self.city or False,
            'state_id': self.state_id.id if self.state_id else False,
            'country_id': self.country_id.id if self.country_id else False,
            'image_1920': self.student_image or False,
            'is_student': True,
        }

    @api.model
    def _get_partner_sync_fields(self):
        return set(self._SYNC_FIELD_MAP)

    @api.model
    def _get_student_sync_fields(self):
        return set(self._SYNC_FIELD_MAP.values())

    def _ensure_related_partner(self):
        for student in self:
            partner = student.partner_id
            if partner and partner.is_parent and not partner.is_student:
                partner = False
            if not partner:
                partner = self.env['res.partner'].search([
                    ('email', '=', student.email),
                    ('is_student', '=', True),
                ], limit=1)
            partner_vals = student._prepare_related_partner_vals()
            if partner:
                partner.with_context(skip_partner_student_sync=True).write(partner_vals)
            else:
                partner = self.env['res.partner'].create(partner_vals)
            partner.is_student = True
            if student.partner_id != partner:
                student.partner_id = partner

    def _sync_to_related_partner(self, vals):
        if self.env.context.get('skip_student_partner_sync'):
            return

        sync_fields = self._get_partner_sync_fields()
        if not any(field in vals for field in sync_fields | {'partner_id'}):
            return

        for student in self:
            student._ensure_related_partner()
            if student.partner_id:
                student.partner_id.with_context(skip_partner_student_sync=True).write(
                    student._prepare_related_partner_vals()
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('barcode'):
                vals['barcode'] = self.env['ir.sequence'].next_by_code(
                    'student.student.sequence'
                )
        students = super(StudentStudent, self).create(vals_list)
        students._ensure_related_partner()
        return students

    def write(self, vals):
        result = super(StudentStudent, self).write(vals)
        self._sync_to_related_partner(vals)
        return result

    @api.constrains('email')
    def _check_email_format(self):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        for record in self:
            if record.email:
                if not re.match(email_regex, record.email):
                    raise ValidationError("The email address is not valid. Please enter a valid email.")

    @api.depends('enrollment_ids.state')
    def _compute_enrollment_grade_id(self):
        for student in self:
            if student.enrollment_ids:
                active_enrollment = self.env['student.enrollment'].search([('student_id', '=', student.id), ('state', '=', 'progress')])
                if active_enrollment:
                    student.current_enrollment_id = active_enrollment
                    student.current_grade_id = active_enrollment.grade_id
                else:
                    student.current_enrollment_id = False
                    student.current_grade_id = False

    @api.depends('enrollment_ids')
    def _compute_no_enrollments(self):
        for record in self:
            record.no_enrollments = len(record.enrollment_ids) == 0

    @api.depends('barcode')
    def _compute_vertical_barcode(self):
        for student in self:
            if not student.barcode:
                student.vertical_barcode_image = False
                continue
            try:
                barcode_drawing = createBarcodeDrawing(
                    'Code128',
                    value=student.barcode,
                    barHeight=40,
                    barWidth=1,
                    humanReadable=False)

                img_data = renderPM.drawToString(barcode_drawing, fmt='PNG')
                img = Image.open(BytesIO(img_data))

                rotated_img = img.rotate(90, expand=True)
                buffer = BytesIO()
                rotated_img.save(buffer, format='PNG')
                student.vertical_barcode_image = base64.b64encode(buffer.getvalue())

            except Exception as e:
                _logger.exception("Failed to generate vertical barcode for student %s", student.name)
                student.vertical_barcode_image = False

    @api.constrains('email')
    def check_for_unique_stuent_email(self):
        for student in self:
            record = self.search([
                ('email', '=', student.email),
                ('id', '!=', student.id)])
            if record:
                raise ValidationError(_(f"Student {student.name} already exists with email {student.email}!."))

    @api.depends('parent_ids.user_ids.active', 'parent_ids.active')
    def _compute_parent_portal_active(self):
        portal_group = self.env.ref('base.group_portal')
        for student in self:
            student.parent_portal_active = False
            for parent in student.parent_ids:
                if not parent.active:
                    continue
                for user in parent.user_ids:
                    if user.active and portal_group in user.group_ids:
                        student.parent_portal_active = True
                        break
                if student.parent_portal_active:
                    break

    def action_create_related_user(self):
        parent_ids = [id for id in self.parent_ids.ids if id]
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Portal User Access',
            'res_model': 'wk.portal.wizard.user',
            'views': [(self.env.ref('wk_school_management.wk_portal_wizard_user_form').id, 'form')],
            'target': 'new',
            'context': {
                'default_student_ids': self.ids,
                'default_parent_ids': parent_ids,
            }
        }
        return action

    def action_revoke_portal_access(self):
        message = (_("Please note: Revoking access for this student will also remove access for any linked parent(s)."))
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Revoke User Access',
            'res_model': 'wk.message.wizard',
            'views': [(self.env.ref('wk_school_management.wk_message_wizard_view_form').id, 'form')],
            'target': 'new',
            'context': {
                'default_message': message
            }
        }
        return action

    def get_student_session(self):
        session = []
        if self.enrollment_ids:
            for enrollment in self.enrollment_ids:
                enrollment.session_id
                if enrollment.session_id not in session:
                    session.append(enrollment.session_id)
        return session

    def get_student_address(self):
        parts = [
            self.street,
            self.street2,
            self.city,
            self.state_id.name if self.state_id else "",
            self.country_id.name if self.country_id else "",
            self.zip
        ]
        return " ".join(filter(None, parts))

    def fetch_transcript_record(self, session=False, student=False, enrollment=False):
        record = []
        if student:
            student_data = self.sudo().browse(int(student))

        company = student_data.company_id
        address_parts = [
            company.street,
            company.city,
            company.state_id.name if company.state_id else '',
            company.country_id.name if company.country_id else ''
        ]
        address = ', '.join(filter(None, address_parts))

        student_information = {
            'name': student_data.name,
            'adress': student_data.get_student_address() if student_data.get_student_address else "",
            'phone_number': student_data.mobile,
            'email': student_data.email,
            'dob': student_data.dob if student_data.dob else "",
            'parent': student_data.father_name if student_data.father_name else "",
        }
        if session:
            session_id = self.env['wk.school.session'].sudo().browse(int(session))

        school_information = {
            'name': student_data.company_id.name,
            'adress': address,
            'phone_number': student_data.company_id.phone,
            'email': student_data.company_id.email,
            'session_name': session_id.name if session_id else "",
            'session_status': session_id.state if session_id else ""
        }
        if enrollment:
            enrollment_data = self.env['student.enrollment'].sudo().browse(int(enrollment))
            data = enrollment_data.get_transcript_enrollment_data()
            dict1 = {'grade': enrollment_data.grade_id.name,
                     'academic_year': enrollment_data.academic_year_id.name,
                     'session': enrollment_data.session_id.name}
            data[0].update(dict1)
            record.append(data)

            return record, student_information, school_information
        else:

            enrollment_ids = student_data.enrollment_ids.sudo().filtered(lambda e: e.session_id.id == int(session)).sorted(key=lambda r: r.id)
            for enrollment in enrollment_ids:
                data = enrollment.get_transcript_enrollment_data()
                dict1 = {'grade': enrollment.grade_id.name,
                         'academic_year': enrollment.academic_year_id.name,
                         'session': enrollment.session_id.name}
                data[0].update(dict1)
                record.append(data)
            return record, student_information, school_information

    def action_print_student_transcript(self):
        self.ensure_one()

        action = {
            'type': 'ir.actions.act_window',
            'name': 'Select Session',
            'res_model': 'wk.student.transcript.wizard',
            'views': [(self.env.ref('wk_school_management.wk_student_transcript_wizard_view_form').id, 'form'), (False, "list"),],
            'target': 'new',
            'context': {
                'default_student_id': self.id,
            }
        }
        return action

    def get_student_transcript_data(self, session=None, student=None):
        record = []
        login_user = self.env.user
        if student:
            student_data = self.sudo().browse(student)
        else:
            student_data = self.sudo().search([('user_id', '=', login_user.id)])

        enrollment_ids = student_data.enrollment_ids.sudo().filtered(lambda e: e.session_id.id == int(session)).sorted(key=lambda r: r.id)
        for enrollment in enrollment_ids:
            data = enrollment.get_transcript_enrollment_data()
            dict1 = {'grade': enrollment.grade_id.name,
                     'academic_year': enrollment.academic_year_id.name,
                     'session': enrollment.session_id.name}
            data[0].update(dict1)
            record.append(data)
        return record

    def _mark_attendance(self, student_id):
        '''
        This method is used to mark attendance for a student.
        :param student_id: ID of the student
        :return: Dictionary containing student name
        '''
        self.ensure_one()
        if student_id:
            student_record = self.sudo().browse(int(student_id))
            today = fields.Date.today()

            attendance_record = self.env['wk.student.attendance'].sudo().search([
                ('student_id', '=', int(student_id)), ('attendance_date', '=', today)])

            if attendance_record:
                if attendance_record.attendance_state == 'present':
                    attendance_record.write({
                        'check_out': fields.Datetime.now(),
                    })

                if attendance_record.attendance_state == 'absent':
                    attendance_record.write({
                                        'attendance_state': 'present',
                                        'check_in': fields.Datetime.now(),
                                        'state': 'lock'
                                    })
            else:
                self.env['wk.student.attendance'].sudo().create({
                    'student_id': student_record.id,
                    'attendance_state': 'present',
                    'check_in': fields.Datetime.now(),
                    'attendance_date': today,
                    'state': 'lock'
                })

            student_details = {
                'student_name': student_record.name
            }
            return student_details
        
    def action_remove_student(self):
        """
        This method is used to remove the student from the transport route.
        It sets the route_id to False for the student.
        """
        for student in self:
            if student.route_id:
                student.route_id = False
            else:
                raise ValidationError(_("This student is not assigned to any transport route."))

    def action_activate_transport(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Transport Route',
            'res_model': 'student.route.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('wk_school_management.student_route_wizard_view_form_activate_student').id,
            'target': 'new',
            'context': {
                'student_company': self.company_id.id,
                'default_location_id': self.location_id.id,
                'default_route_id': self.route_id.id,
            }
        }
        
    def action_deactivate_transport(self):
        for rec in self:
            rec.write({
                'is_transport_enabled': False,
                'location_id': False,
                'route_id': False
            })
            
    def action_activate_transport_bulk(self):
        if any(student.is_transport_enabled for student in self):
            raise UserError("Transposrt for some student is already enabled So please select students whose Transport is not enabled.")
        else:
            return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Transport Route',
            'res_model': 'student.route.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('wk_school_management.student_route_wizard_view_form_activate_student').id,
            'target': 'new',
            'context': {
                'student_company': self.company_id.id,
                'default_location_id': self.location_id.id,
                'default_route_id': self.route_id.id,
                'bulk_activation': True,
                },  
            }
