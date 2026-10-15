# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EnrollWizard(models.TransientModel):

    _name = 'wk.enroll.wizard'
    _description = 'Shows options for creating enrollments'

    enroll_action = fields.Selection([
        ('new', 'Create a new student'),
        ('exist', 'Link to an existing student'),
    ], string='Enroll', default="new", required=True)
    student_id = fields.Many2one('student.student', 'Student')

    def enroll_now(self):
        self.ensure_one()
        application_id = self.env.context.get('active_id')
        application = self.env['wk.application.form'].browse(application_id)
        if self.enroll_action == 'new':
            student_exist = self.env['student.student'].search(
                [('application_id', '=', application_id)])
            if student_exist:
                raise UserError(
                    _('This student already exists! Please move ahead by selecting existing student.'))
            else:
                details = {
                    'name': application.student_name,
                    'student_image': application.student_image,
                    'company_id': application.company_id.id,
                    'application_id': application.id,
                    'gender': application.gender,
                    'dob': application.dob,
                    'mother_name': application.mother_name,
                    'father_name': application.father_name,
                    'mothers_contact': application.mothers_contact,
                    'fathers_contact': application.fathers_contact,
                    'mothers_occupation': application.mothers_occupation,
                    'fathers_occupation': application.fathers_occupation,
                    'parent_email': application.parent_email,
                    'email': application.email,
                    'mobile': application.phone,
                    'street': application.street,
                    'street2': application.street2,
                    'city': application.city,
                    'state_id': application.state_id.id,
                    'country_id': application.country_id.id,
                    'country_code': application.country_code,
                    'zip': application.zip,
                    'attachment_ids': [(6, 0, application.attachment_ids.ids)]
                }
                student = self.env['student.student'].sudo().create(details)
                for attachment in application.attachment_ids:
                    attachment.write({
                        'res_model': 'student.student',
                        'res_id': student.id,
                    })
                application.write({
                    'student_id': student.id, })

                action = {
                    'type': 'ir.actions.act_window',
                    'res_model': 'student.enrollment',
                    'views': [(self.env.ref('wk_school_management.student_enrollment_form').id, 'form')],
                    'context': {'default_student_id': student.id,
                                'grade_id': application.grade_id.id,
                                'application_form_id': application.id,
                                'update': 1}
                }
                return action

        elif self.enroll_action == 'exist':
            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'student.enrollment',
                'views': [(self.env.ref('wk_school_management.student_enrollment_form').id, 'form')],
                'context': {'default_student_id': self.student_id.id,
                            'application_form_id': application.id,
                            'update': 1}
            }
            return action


class StudentPromoteWizard(models.TransientModel):

    _name = 'wk.student.promote'
    _inherit = 'wk.section.visibility.mixin'
    _description = 'Student Promote Wizard'

    current_grade_id = fields.Many2one(
        'wk.school.grade', string='Current Grade')
    grade_id = fields.Many2one(
        'wk.school.grade', string='New Grade', required=True)
    section_id = fields.Many2one(
        "wk.grade.section", string="Section", domain="[('grade_id', '=', grade_id)]")
    student_id = fields.Many2one('student.student', string="Student")
    session_id = fields.Many2one('wk.school.session', string="Session",
        required=True, domain="[('state', '!=', 'complete')]")
    academic_year_id = fields.Many2one('wk.academic.year', string='Academic Year',
        domain="[('session_id', '=', session_id)]", required=True)
    student_ids = fields.Many2many('student.student', string='Students')

    def promote_student(self):
        self.ensure_one()
        active_ids = self.env.context.get('active_ids', [])
        enrollments = self.env['student.enrollment'].browse(active_ids)
        fee_structure = self.env['fee.structure'].search([
            ('grade_id', '=', self.grade_id.id)], limit=1)

        if len(enrollments) == 1:
            enrollment = enrollments[0]
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'student.enrollment',
                'views': [(self.env.ref('wk_school_management.student_enrollment_form').id, 'form')],
                'context': {
                    'default_student_id': enrollment.student_id.id,
                    'default_academic_year_id': self.academic_year_id.id,
                    'default_session_id': self.session_id.id,
                    'default_section_id': self.section_id.id,
                    'default_grade_id': self.grade_id.id,
                    'default_fee_structure_id': fee_structure.id,
                    'promote': True,
                    'from_enrollment_id': enrollment.id,
                }
            }
        for enrollment in enrollments:
            self.env['student.enrollment'].create({
                'student_id': enrollment.student_id.id,
                'academic_year_id': self.academic_year_id.id,
                'session_id': self.session_id.id,
                'grade_id': self.grade_id.id,
                'section_id': self.section_id.id,
                'fee_structure_id': fee_structure.id,
            })
            enrollment.state = 'promote'
        return True


class StudentEnrollmentSubjectWizard(models.TransientModel):

    _name = 'wk.student.enrollment.subject'
    _description = 'Student Enrollment Subjects'

    subject_ids = fields.Many2many('wk.grade.subjects', string='Subject', domain="[('grade_id','=',grade_id)]")
    grade_id = fields.Many2one(
        'wk.school.grade', string='Grade')

    def add_subject_wizard(self):
        active_id = self.env.context.get("active_id")
        for subject in self.subject_ids:
            self.env['wk.student.subjects'].create({'subject_id': subject.id,
                                                    'enrollment_id': active_id})
