# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo.http import request
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class WkStudentScholarship(models.Model):

    _name = "wk.student.scholarship"
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'wk.section.visibility.mixin', 
                'wk.company.visibility.mixin']
    _description = "Student Scholarship"
    _order = "write_date desc"

    name = fields.Char(string="Name", required=True,
            copy=False, default=lambda self: _('New'), readonly=True)
    student_id = fields.Many2one('student.student', string='Student', required=True)
    enrollment_id = fields.Many2one(string="Enrollment No.",
        related='student_id.current_enrollment_id', store=True)
    grade_id = fields.Many2one(string="Grade",
        related='student_id.current_enrollment_id.grade_id', store=True)
    section_id = fields.Many2one(string="Section", 
        related='student_id.current_enrollment_id.section_id', store=True)
    current_academic_year_id = fields.Many2one(
        string='Academic Year', related='student_id.current_enrollment_id.academic_year_id')
    scholarship_amount = fields.Monetary(string='Amount', required=True,
        currency_field='currency_id', tracking=True)
    paid_date = fields.Date(string="Paid Date", readonly=True)
    state = fields.Selection([
        ('new', 'New'),
        ('approve', 'Approved'),
        ('paid', 'Paid'),
        ('cancel', 'Cancelled')
    ], string='Status', default="new", readonly=True, tracking=True)
    company_id = fields.Many2one('res.company', string="School",
        required=True, default=lambda self: self.env.company)
    invoice_id = fields.Many2one('account.move', string="Invoice", tracking=True)
    invoice_status = fields.Selection(related='invoice_id.payment_state')
    approver_id = fields.Many2one('hr.employee', string="Approved By",
                                  domain="[('is_teacher','=',True)]", readonly=True)
    currency_id = fields.Many2one(
        string='Currency', related='company_id.currency_id', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            scholarship_amount = vals.get('scholarship_amount')
            if scholarship_amount <= 0:
                raise ValidationError(_("The scholarship amount must be greater than 0."))
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'wk.student.scholarship.sequence') or _("New")
        return super().create(vals_list)

    @api.constrains('scholarship_amount')
    def check_for_scholarship_amount(self):
        for record in self:
            if record.scholarship_amount <= 0:
                raise ValidationError(
                    _("The scholarship amount must be greater than 0."))

    def approve_scholarship(self):
        for scholarship in self:
            if scholarship.state == 'new':
                scholarship.state = 'approve'
                approver = self.env.user
                scholarship.approver_id = approver.employee_id

    def pay_scholarship(self):
        for scholarship in self:
            if not scholarship.invoice_status == 'paid':
                raise UserError(
                    _(f"The invoice {scholarship.invoice_id.name} is still unpaid.Please mark it paid first."))
            scholarship.state = 'paid'
            scholarship.paid_date = fields.Date.today()

    def cancel_scholarship(self):
        for scholarship in self:
            scholarship.state = 'cancel'

    def reset_scholarship(self):
        for scholarship in self:
            scholarship.state = 'new'

    def generate_in_invoice(self):
        self.ensure_one()
        scholarship_product = request.env['res.config.settings'].sudo().get_values().get('scholarship_product_id')
        partner = self.student_id.partner_id or self.student_id.user_id.partner_id
        if not partner:
            raise UserError(
                _("The student does not have a valid associated customer record."))

        if not scholarship_product:
            raise UserError(
                _("There is no element selected for scholarship.Please select one in configuration."))

        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': scholarship_product,
                'quantity': 1,
                'price_unit': self.scholarship_amount,
            })],
            'company_id': self.company_id.id,
        }
        invoice = self.env['account.move'].create(invoice_vals)
        invoice.action_post()
        self.invoice_id = invoice.id

    def action_scholarship_paid(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Scholarships',
            'views': [(self.env.ref('wk_school_management.scholarship_display_view_form').id, 'form')],
            'res_model': 'wk.scholarship.update.wizard',
            'target': 'new',
            'context': {
                'default_scholarship_ids': self.ids,
            }}
