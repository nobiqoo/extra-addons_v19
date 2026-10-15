# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

import logging
import base64
import qrcode
from io import BytesIO
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StudentEnrollmentForm(models.Model):
    _name = 'student.enrollment'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'wk.section.visibility.mixin',
                'wk.company.visibility.mixin']

    _description = 'Enrollment Form'
    _order = "write_date desc"

    name = fields.Char(
        string="Enrollment No.",
        required=True, copy=False, readonly=False,
        default=lambda self: _('New'))

    state = fields.Selection([
        ('draft', 'Draft'),
        ('progress', 'In Progress'),
        ('complete', 'Completed'),
        ('cancel', 'Cancelled'),
        ('promote', 'Promoted'),
        ('terminate', 'Terminated'),
        ], string='Enrollment Status', default="draft", readonly=True, tracking=True)
    student_id = fields.Many2one('student.student', required=True, string='Student', default=lambda self: self.env.context.get('student_id'))
    enrollment_date = fields.Date(string="Enrollment Date", default=fields.Date.context_today)
    session_id = fields.Many2one('wk.school.session', string="Session", required=True, domain="[('state', '!=', 'complete')]",)
    company_id = fields.Many2one('res.company', string="School", required=True, default=lambda self: self.env.company)
    grade_id = fields.Many2one('wk.school.grade', string="Grade", required=True, default=lambda self: self.env.context.get('grade_id'))
    section_id = fields.Many2one("wk.grade.section", 
        string="Section", domain="[('grade_id', '=', grade_id)]")
    payment_term = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annualy', 'Annually'),
        ('custom', 'Custom')
        ], string='Payment Term')
    fee_structure_id = fields.Many2one('fee.structure', string='Fee Structure', required=True, domain="[('grade_id','=',grade_id)]")
    application_form_id = fields.Many2one('wk.application.form', string="Application Form", default=lambda self: self.env.context.get('application_form_id'))
    student_subject_ids = fields.One2many('wk.student.subjects', 'enrollment_id', string='Subjects')
    student_image = fields.Image('Image', related='student_id.student_image', store=True)
    session_status = fields.Selection(related='session_id.state', string='Session Status', store=True)

    academic_year_id = fields.Many2one('wk.academic.year', string='Academic Year', domain="[('session_id', '=', session_id)]", required=True)
    service_hour_ids = fields.One2many('wk.service.hours', 'enrollment_id', string='Service Hours')
    discipline_ids = fields.One2many('wk.student.discipline', 'enrollment_id', string="Discipline")
    total_hours = fields.Float(string="Total Hours", compute='_compute_total_hours', store=True)
    approved_hours = fields.Float(string="Approved Hours", compute='_compute_total_hours', store=True)

    fee_summary_ids = fields.One2many('wk.fee.summary', 'enrollment_id', string='Fee Summary')
    fee_slip_ids = fields.One2many('wk.fee.slip', 'enrollment_id', string='Fee Slips')
    scholarship_ids = fields.One2many('wk.student.scholarship', 'enrollment_id', string='Scholarships')
    qr_code = fields.Binary(string='QR Code')
    installment = fields.Integer(string="Installments")
    fee_status = fields.Selection([
        ('to_pay', 'To Pay'),
        ('partially', 'Partially Paid'),
        ('fully', 'Fully Paid'),
        ('overdue', 'Overdue')
        ], string='Fee Status', default="to_pay", required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='fee_structure_id.currency_id', store=True)
    total_amount = fields.Monetary(string='Total Fee', compute='_compute_fee_amount',
                                   store=True, currency_field='currency_id', tracking=True)
    paid_amount = fields.Monetary(string='Paid Fee', compute='_compute_fee_amount',
                                  store=True, currency_field='currency_id', tracking=True)
    due_amount = fields.Monetary(string='Due Fee', compute='_compute_fee_amount',
                                 store=True, currency_field='currency_id')
    generated_amount = fields.Monetary(string='Fee Slip Amount', compute='_compute_fee_amount',
                                       store=True, currency_field='currency_id')
    fee_slip_count = fields.Integer(
        string='Fee Slip Count', compute='_compute_fee_slip_count')
    assignment_count = fields.Integer(
        string='Assignment Count', compute='_compute_assignment_count')
    term_id = fields.Many2one('wk.grade.terms', string='Term',
        domain="[('academic_year_id', '=', academic_year_id)]", ondelete='cascade')

    def generate_qr_code(self):
        "method to generate QR code"
        for enrollment in self:
            if qrcode and base64 and not enrollment.qr_code:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=6,
                    border=4,
                )
                qr.add_data('/student/kiosk/attendance/')
                qr.add_data(enrollment.name)
                qr.make(fit=True)
                img = qr.make_image()
                temp = BytesIO()
                img.save(temp, format="PNG")
                qr_image = base64.b64encode(temp.getvalue())
                enrollment.update({'qr_code': qr_image})

    @api.model_create_multi
    def create(self, vals_list):
        val = self.env.context.get('update', False)
        if val:
            application = self.env.context.get('application_form_id')
            application = self.env['wk.application.form'].browse(application)
            application.write({'state': 'enroll'})
            mail_template = self.env.ref('wk_school_management.application_enrollment_mail', raise_if_not_found=False)
            if mail_template:
                mail_template.send_mail(application.id, force_send=True)
        if self.env.context.get('promote') and self.env.context.get('from_enrollment_id'):
            previous = self.env['student.enrollment'].browse(self.env.context['from_enrollment_id'])
            if previous:
                previous.state = 'promote'

        return super().create(vals_list)

    @api.depends('service_hour_ids.state')
    def _compute_total_hours(self):
        for record in self:
            record.approved_hours = 0
            record.total_hours = 0
            for hours in record.service_hour_ids:
                if hours.state == 'approve':
                    record.approved_hours += hours.total_hours
                if hours.state == 'approve' or hours.state == 'new':
                    record.total_hours += hours.total_hours

    @api.depends('student_subject_ids.total_assignments')
    def _compute_assignment_count(self):
        for enrollment in self:
            enrollment.assignment_count = sum(subject.total_assignments for subject in enrollment.student_subject_ids)

    @api.depends('fee_slip_ids')
    def _compute_fee_slip_count(self):
        for enrollment in self:
            if enrollment.fee_slip_ids:
                enrollment.fee_slip_count = len(enrollment.fee_slip_ids)
            else:
                enrollment.fee_slip_count = 0

    @api.depends('fee_summary_ids.fee', 'fee_slip_ids.state')
    def _compute_fee_amount(self):
        for enrollment in self:
            total_amount = 0.0
            paid_amount = 0.0
            generated_amount = 0.0

            for summary in enrollment.fee_summary_ids:
                total_amount += summary.fee
            for slip in enrollment.fee_slip_ids:
                generated_amount += slip.total_amount
                if slip.state == 'paid':
                    paid_amount += slip.total_amount
            # Determine fee status based on amounts
            if paid_amount > 0 and paid_amount < total_amount:
                enrollment.fee_status = 'partially'
                # Update amount_paid in fee_summary_ids based on paid slips
                for summary in enrollment.fee_summary_ids:
                    paid = 0.0
                    for slip in enrollment.fee_slip_ids.filtered(lambda s: s.state == 'paid'):
                        for line in slip.fee_slip_line_ids.filtered(lambda l: l.product_id == summary.product_id):
                            paid += line.fee
                    summary.amount_paid = paid
            elif paid_amount >= total_amount and total_amount > 0:
                enrollment.fee_status = 'fully'
            elif paid_amount == 0 and generated_amount > 0:
                enrollment.fee_status = 'to_pay'
            elif generated_amount > 0 and paid_amount == 0:
                enrollment.fee_status = 'overdue'

            enrollment.total_amount = total_amount
            enrollment.generated_amount = generated_amount
            enrollment.paid_amount = paid_amount
            enrollment.due_amount = total_amount - paid_amount

    @api.onchange('grade_id')
    def onchange_grade_id(self):
        self.student_subject_ids = False
        fee_structure = self.env['fee.structure'].search([('grade_id', '=', self.grade_id.id)], limit=1)

        if fee_structure:
            self.fee_structure_id = fee_structure
        else:
            self.fee_structure_id = False

    @api.onchange('session_id')
    def onchange_session_id(self):
        if self.session_id and self.academic_year_id:
            if self.academic_year_id.session_id != self.session_id:
                self.academic_year_id = False

    @api.onchange('fee_structure_id')
    def onchange_fee_structure_id(self):
        self.fee_summary_ids = [(5, 0, 0)]
        values = []
        fee_structure_id = self.fee_structure_id
        components = fee_structure_id.fee_component_ids
        for component in components:
            summary_data = {
                'product_id': component.product_id,
                'fee': component.fee,
                'frequency': component.frequency,
                'sequence': component.sequence,
            }
            values.append((0, 0, summary_data))

        self.fee_summary_ids = values

    @api.constrains('student_id', 'grade_id')
    def check_for_unique_grade_enrollment(self):
        for enrollment in self:
            record = self.search([
                ('student_id', '=', enrollment.student_id.id),
                ('grade_id', '=', enrollment.grade_id.id),
                ('id', '!=', enrollment.id)])
            if record:
                raise ValidationError(_(f"Enrollment for {enrollment.student_id.name} in grade {enrollment.grade_id.name} already exists!"))

    def confirm_enrollment(self):
        for obj in self:
            if obj.state != 'draft':
                raise UserError(_("Only new application can be marked as confirm."))

            existing_enrollment = self.search([('student_id', '=', obj.student_id.id), ('state', '=', 'progress')])
            if existing_enrollment:
                raise UserError(_(f"{obj.student_id.name} already has an in progress enrollment.Please mark it complete to start this one"))

            if obj.name == 'New':
                values = {
                    'name':  self.env['ir.sequence'].next_by_code('enrollment.form') or _('New'),
                    'state': 'progress'
                }
            else:
                values = {
                    'state': 'progress'
                }

            obj.write(values)
            obj.generate_qr_code()
        return True

    def reset_enrollment(self):
        for obj in self:
            if obj.state == 'complete':
                existing_enrollment = self.search([
                    ('student_id', '=', obj.student_id.id),
                    ('state', '=', 'progress'),
                    ('id', '!=', obj.id)
                ])
                if existing_enrollment:
                    raise ValidationError(_(f"{obj.student_id.name} already has an in progress enrollment. Please mark it complete to reset this one."))
                obj.state = 'progress'
            else:
                obj.state = 'draft'
        return True

    def cancel_enrollment(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Reason',
            'res_model': 'cancel.reset.reason',
            'views': [(self.env.ref('wk_school_management.cancel_enrollment_reason_view').id, 'form')],
            'target': 'new',
        }
        return action

    def complete_enrollment(self):
        for obj in self:
            obj.state = 'complete'
        return True

    def promote_enrollment(self):
        name = self.env.context.get('default_name')
        action = self.env["ir.actions.act_window"]._for_xml_id("wk_school_management.student_promote_action")

        for record in self:
            if record.fee_status != 'fully':
                raise ValidationError(_(f"Fee slip status of student {record.student_id.name} must be fully paid to promote the student."))

        if name == 'single':
            action['context'] = {
                'default_student_id': self.student_id.id,
                'default_current_grade_id': self.grade_id.id,
            }
        else:
            student_ids = self.env['student.student'].search([('enrollment_ids', 'in', self.ids)])
            action['context'] = {
                'default_student_ids': student_ids.ids,
                'default_current_grade_id': self.grade_id.id,
            }
        return action
    
    def terminate_enrollment(self):
        for enrollment in self:
            if enrollment.state != 'complete':
                raise UserError(_("Only completed enrollments can be terminated."))
            if enrollment.fee_status != 'fully':
                raise ValidationError(_(f"Fee slip status of student {enrollment.student_id.name} must be fully paid to terminate the student."))
            enrollment.student_id.active = False
            enrollment.state = 'terminate'

    def generate_schedule_fees(self):
        self.ensure_one()
        if self.academic_year_id.start_date < fields.Date.today():
            start_date = fields.Date.today()
        else:
            start_date = self.academic_year_id.start_date

        if self.academic_year_id.end_date < fields.Date.today():
            end_date = fields.Date.today()
        else:
            end_date = self.academic_year_id.end_date
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fee Slip',
            'res_model': 'wk.fee.generate.wizard',
            'views': [(self.env.ref('wk_school_management.wk_fee_generate_wizard_view_form').id, 'form')],
            'target': 'new',
            'context': {'default_enrollment_id': self.id,
                        'default_amount_to_pay': self.total_amount,
                        'default_start_date': start_date,
                        'default_end_date': end_date,
                    },
        }
    
    def get_assignments(self):
        self.ensure_one()
        assignments = self.env['wk.student.assignment'].search([('student_subject_id', 'in', self.student_subject_ids.ids)])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assignments',
            'res_model': 'wk.student.assignment',
            'domain': [('id', 'in', assignments.ids)],
            'view_mode': 'list,form',
        }
    
    def get_reports(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reports',
            'res_model': 'wk.student.subjects',
            'view_mode': 'list,form',
            'domain': [('enrollment_id', '=', self.id)],
        }

    def get_student_record(self, session=False):
        enrollment_data = self.search([('session_id', '=', session)])
        student_data = set()
        if enrollment_data:
            for enrollment in enrollment_data:
                student = (enrollment.student_id.id, enrollment.student_id.name)
                student_data.add(student)
        return list(student_data)

    def get_transcript_enrollment_data(self):
        report_data = []
        for enrollment in self:
            term_list = []
            terms = sorted(enrollment.academic_year_id.term_ids, key=lambda t: t.start_date)
            term_averages = {
                term.id: {
                    'total_weighted_points': 0.0,
                    'total_credits': 0.0
                } for term in terms
            }
            for term in terms:
                term_subjects = []

                for subject_line in enrollment.student_subject_ids:
                    subject = subject_line.subject_id
                    credit_value = subject.credit_value or 0
                    grade = ''
                    point_obtained = None
                    for report in subject_line.term_report_ids:
                        if report.term_id == term:
                            grade = report.scale_line_id.grade_symbol or ''
                            point_obtained = report.point_obtained
                            break

                    if point_obtained is not None:
                        weighted_points = point_obtained * credit_value
                        term_averages[term.id]['total_weighted_points'] += weighted_points
                        term_averages[term.id]['total_credits'] += credit_value

                    term_subjects.append({
                        'subject_code': subject.subject_code if subject.subject_code else "",
                        'subject_name': subject.name,
                        'credit_value': credit_value,
                        'grade': grade
                    })

                term_list.append({
                    'name': term.name,
                    'id': term.id,
                    'subjects': term_subjects,
                    'sgpa': 0.0,
                    'cgpa': 0.0
                })
            average_points = {
                term_id: (
                    round(data['total_weighted_points'] / data['total_credits'], 2)
                    if data['total_credits'] > 0 else 0.0
                ) for term_id, data in term_averages.items()
            }
            cgpa_by_term = {}
            cumulative_points = 0.0
            cumulative_credits = 0.0

            for term in terms:
                term_id = term.id
                weightage = term.weightage or 0
                sgpa = average_points.get(term_id, 0.0)

                cumulative_points += sgpa * weightage
                cumulative_credits += weightage

                cgpa = round(cumulative_points / cumulative_credits, 2) if cumulative_credits else 0.0
                cgpa_by_term[term_id] = cgpa
                for t in term_list:
                    if t['id'] == term_id:
                        t['sgpa'] = sgpa
                        t['cgpa'] = cgpa
            report_data.append({
                'enrollment': enrollment.name,
                'academic_year': enrollment.academic_year_id.name,
                'grade': enrollment.grade_id.name,
                'terms': term_list,
            })
        return report_data

    def get_termwise_report(self):
        report_data = []
        for enrollment in self:
            if enrollment.term_id:
                terms = enrollment.term_id
                is_single_term = True
            else:
                terms = sorted(enrollment.academic_year_id.term_ids, key=lambda t: t.start_date)
                is_single_term = False

            subject_data = {}

            term_averages = {
                term.id: {
                    'total_weighted_points': 0,
                    'total_credits': 0
                } for term in terms
            }

            for subject in enrollment.student_subject_ids:
                credit_value = subject.credit_value or 0
                subject_data[subject.id] = {
                    'subject_name': subject.subject_id.name,
                    'terms': {},
                    'credit_value': credit_value,
                    'subject_code': subject.subject_code
                }
                for term in terms:
                    term_report = next(
                        (tr for tr in subject.term_report_ids if tr.term_id == term),
                        None)

                    if term_report:
                        grade_scale_line = term_report.scale_line_id
                        effort = grade_scale_line.effort if grade_scale_line else ""
                        grade_symbol = grade_scale_line.grade_symbol if grade_scale_line else ""

                        subject_data[subject.id]['terms'][term.id] = {
                            'grade': grade_symbol,
                            'effort': effort
                        }

                        weighted_points = term_report.point_obtained * credit_value
                        term_averages[term.id]['total_weighted_points'] += weighted_points
                        term_averages[term.id]['total_credits'] += credit_value

                    elif not is_single_term:
                        subject_data[subject.id]['terms'][term.id] = {
                            'grade': '',
                            'effort': ''
                        }
            average_points = {
                term_id: (
                    round(data['total_weighted_points'] / data['total_credits'], 2)
                    if data['total_credits'] > 0 else 0
                ) for term_id, data in term_averages.items()}
            cgpa_by_term = {}
            cumulative_points = 0
            cumulative_credits = 0

            for i, term in enumerate(terms):
                term_id = term.id
                term_gpa = average_points.get(term_id, 0)
                if i == 0:
                    cgpa_by_term[term_id] = term_gpa
                    cumulative_points += term_gpa * (term.weightage or 0)
                    cumulative_credits += (term.weightage or 0)
                else:
                    cumulative_points += term_gpa * (term.weightage or 0)
                    cumulative_credits += (term.weightage or 0)
                    cgpa_by_term[term_id] = round(cumulative_points / cumulative_credits, 2) if cumulative_credits else 0

            scale_lines = []
            if enrollment.grade_id and enrollment.grade_id.scale_id:
                scale_lines = self.env['wk.grade.scale.line'].search([
                    ('scale_id', '=', enrollment.grade_id.scale_id.id)
                ])

            report_data.append({
                'enrollment': enrollment,
                'terms': terms,
                'subjects': subject_data,
                'grade_scale_lines': scale_lines,
                'averages': average_points,
                'cgpa_by_term': cgpa_by_term
            })
        return report_data

    def get_student_subject(self):
        grade_summary = []
        if self.student_subject_ids:
            for subject in self.student_subject_ids:
                subject_enrolled = subject.subject_id
                comp_assignments = self.env['wk.student.assignment'].search_count(['&', '&', ('student_subject_id', '=', subject.id), ('subject_id', '=', subject.subject_id.id), '|', ('state', '=', 'submit'), ('state', '=', 'evaluate')])
                incomp_assignments = self.env['wk.student.assignment'].search_count([('student_subject_id', '=', subject.id), ('subject_id', '=', subject.subject_id.id), ('state', '=', 'new')])
                total_assignment = comp_assignments + incomp_assignments
                if subject.scale_line_id.conversion_percent:
                    current_grade = subject.scale_line_id.conversion_percent
                else:
                    current_grade = 0

                grade_summary.append({
                        'subject_name': subject_enrolled.name,
                        'current_grade': current_grade,
                        'incomplete_assignment': incomp_assignments,
                        'completed_assignment': comp_assignments,
                        'total_assignment': total_assignment,
                        'id': subject.subject_id.id
                    })
        return grade_summary

    def promote_bulk_enrollments(self):
        grade_id = self.mapped('grade_id')
        academic_year_id = self.mapped('academic_year_id')
        session_id = self.mapped('session_id')

        if len(grade_id) > 1 or len(academic_year_id) > 1 or len(session_id) > 1:
            raise ValidationError(_('The enrollments selected by you do not belong to the same Grade of same Academic year and Session.'))

        for enrollment in self:
            if enrollment.state != 'complete':
                raise UserError(_("Only completed enrollments can be promoted."))
        action = self.promote_enrollment()
        return action

    def complete_bulk_enrollments(self):
        grade_id = self.mapped('grade_id')
        academic_year_id = self.mapped('academic_year_id')
        session_id = self.mapped('session_id')

        if len(grade_id) > 1 or len(academic_year_id) > 1 or len(session_id) > 1:
            raise ValidationError(_('The enrollments selected by you do not belong to the same Grade of same Academic year and Session.'))

        for enrollment in self:
            if enrollment.state != 'progress':
                raise UserError(_("Only in progress enrollments can be marked as completed."))
            enrollment.state = 'complete'

    def add_subjects(self):
        self.ensure_one()
        subject_ids = self.env['wk.grade.subjects'].search([('grade_id', '=', self.grade_id.id)])
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Add Subjects',
            'res_model': 'wk.student.enrollment.subject',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_grade_id': self.grade_id.id,
                        'default_subject_ids': ([(6, 0, subject_ids.ids)])},
            'views': [[self.env.ref('wk_school_management.student_enrollment_subject_view_form').id, 'form']],
        }
        return action

    def get_fee_slips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fee Slips',
            'res_model': 'wk.fee.slip',
            'domain': [('enrollment_id', '=', self.id)],
            'views': [(self.env.ref('wk_school_management.wk_fee_slip_view_tree').id, 'list'), (False, 'form')],
            'context': {
                'default_student_id': self.student_id.id,
                'default_enrollment_id': self.id,
                'default_grade_id': self.grade_id.id,
                'default_section_id': self.section_id.id,
                'default_academic_year_id': self.academic_year_id.id,
                'default_session_id': self.session_id.id,
                'default_currency_id': self.fee_structure_id.currency_id.id
            }
        }
