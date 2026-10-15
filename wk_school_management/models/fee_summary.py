# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from datetime import timedelta, date
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FeeSummary(models.Model):

    _name = "wk.fee.summary"
    _description = "Fee Summary"

    product_id = fields.Many2one('product.product', string="Fee Element",
                                 required=True, domain="[('is_fee_element','=',True)]")
    fee = fields.Float(string="Fee", required=True)
    sequence = fields.Integer(required=True, default=10)
    frequency = fields.Selection(
        [('one', 'Once'), ('multi', 'Recurring')], string="Frequency", required=True)
    amount_paid = fields.Float(string="Amount Paid", required=True)
    enrollment_id = fields.Many2one(
        'student.enrollment', string="Enrollment No.")
    slip_generated = fields.Boolean(string='Slip Generated')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.fee = self.product_id.lst_price


class FeeSlip(models.Model):

    _name = "wk.fee.slip"
    _inherit = ['mail.thread', 'mail.activity.mixin', 
                'portal.mixin', 
                'wk.section.visibility.mixin',
                'wk.company.visibility.mixin']
    _description = "Fee Slip of Students"
    _order = "write_date desc"

    name = fields.Char(
        string="Serial No.",
        required=True, copy=False, readonly=True,
        default=lambda self: _('/'))
    enrollment_id = fields.Many2one(
        'student.enrollment', string="Enrollment No.")
    student_id = fields.Many2one(
        string='Student', related='enrollment_id.student_id', store=True)
    grade_id = fields.Many2one(
        string="Grade", related='enrollment_id.grade_id', store=True)
    section_id = fields.Many2one(
        string="Section", related='enrollment_id.section_id', store=True)
    academic_year_id = fields.Many2one(
        string='Academic Year', related='enrollment_id.academic_year_id', store=True)
    session_id = fields.Many2one(
        string="Session", related='enrollment_id.session_id', store=True)
    state = fields.Selection([
        ('new', 'New'),
        ('to_pay', 'To Pay'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancel', 'Cancelled')
    ], string='Status', default="new", required=True, tracking=True)
    fee_slip_line_ids = fields.One2many(
        'wk.fee.slip.lines', 'fee_slip_id', string='Fee Summary', required=True)
    total_amount = fields.Float(
        string="Amount", compute='compute_total_amount_per_slip')
    date_from = fields.Date(string="Date From", required=True)
    date_to = fields.Date(string="Date To", required=True)
    description = fields.Html(string="Terms and Conditions",
                              related='enrollment_id.fee_structure_id.description')
    currency_id = fields.Many2one(string="Currency",
                                  related='enrollment_id.fee_structure_id.currency_id')
    transaction_ids = fields.Many2one('payment.transaction', string="Payment", compute="_compute_transaction_ids")
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    invoice_ids = fields.One2many(
        'account.move', 'fee_slip_id', string="Invoices")
    paid_amount = fields.Float(
        string="Paid Amount", compute="_compute_paid_amount")


    def unlink(self):
        for slip in self:
            if slip.state == 'paid':
                raise UserError(_('A paid fee slip cannot be deleted!!'))
        return super().unlink()

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError("The 'Date From' must be earlier than or equal to 'Date To'.")

    @api.constrains('date_from', 'date_to', 'enrollment_id')
    def _check_date_overlap(self):
        for slip in self:
            if not slip.enrollment_id or not slip.date_from or not slip.date_to:
                continue

            domain = [
                ('id', '!=', slip.id),
                ('enrollment_id', '=', slip.enrollment_id.id),
                ('date_from', '<=', slip.date_to),
                ('date_to', '>=', slip.date_from),
            ]
            overlapping = self.search(domain)
            if overlapping:
                raise ValidationError(
                    "Date range overlaps with another fee slip for the same enrollment."
                )

    @api.depends('fee_slip_line_ids.fee')
    def compute_total_amount_per_slip(self):
        for lines in self:
            if lines.fee_slip_line_ids:
                for line in lines.fee_slip_line_ids:
                    lines.total_amount += line.fee
            else:
                lines.total_amount = 0

    @api.depends('invoice_ids.amount_residual', 'invoice_ids.amount_total')
    def _compute_paid_amount(self):
        for slip in self:
            if slip.invoice_ids:
                posted_invoices = slip.invoice_ids.filtered(lambda inv: inv.state == 'posted')
                slip.paid_amount = 0.0

                for inv in posted_invoices:
                    total = inv.amount_total or 1
                    paid_ratio = (total - inv.amount_residual) / total
                    slip.paid_amount += inv.amount_untaxed * paid_ratio
            else:
                slip.paid_amount = 0

    def _sync_payment_state(self):
        """Sincroniza el estado del slip con los pagos reales de sus facturas.

        Se invoca desde cualquier conciliación contable (hook de
        account.move.line) y desde el wizard de registro de pagos, de modo
        que el estado quede correcto sin importar la ruta por la que se
        pagó la factura (wizard, extracto bancario, conciliación manual,
        nota de crédito, etc.).
        """
        for slip in self:
            if slip.state == 'cancel':
                continue
            posted_invoices = slip.invoice_ids.filtered(
                lambda inv: inv.state == 'posted')
            if not posted_invoices:
                continue
            currency = slip.currency_id or slip.company_id.currency_id
            actual_paid = sum(
                inv.amount_total - inv.amount_residual
                for inv in posted_invoices)
            if currency.is_zero(actual_paid):
                continue
            total = slip.total_amount or 0.0
            new_state = 'paid' if currency.compare_amounts(
                actual_paid, total) >= 0 else 'partial'
            if slip.state != new_state:
                slip.state = new_state

    def _has_fee_portal_access(self, student):
        if student.user_id:
            return True

        parent_users = student.parent_ids.mapped('user_ids')
        if parent_users:
            return True

        return False

    def confirm_fee_slip(self):
        for slip in self:
            student = slip.student_id
            if not self._has_fee_portal_access(student):
                raise UserError(_(
                    f"The student {student.name} does not have any portal access "
                    f"(student or parent). Please provide portal access to proceed!"
                ))
            if slip.state == 'new':
                values = {
                    'state': 'to_pay',
                    'name': self.env['ir.sequence'].next_by_code('wk.fee.slip.sequence') or _('/'),
                }
                slip.write(values)

            library_fees = self.env['book.library.fine'].search([('create_date', '>=', slip.date_from), ('create_date', '<=', slip.date_to),('student_id', '=', slip.student_id.id), ('status', '=', 'draft')])
            if library_fees:
                product = self.env['product.product'].search([('libray_element', '=', True)])
                slip_line = self.env['wk.fee.slip.lines'].create(
                    {
                        'product_id': product.id if product else False,
                        'fee': sum(library_fees.mapped('fine')),
                        'fee_slip_id': slip.id,
                    }
                )

    def fee_slip_update(self):
        no_of_days = self.env['res.config.settings'].sudo(
        ).get_values().get('no_of_days')
        today = fields.Date.today()
        slip_ids = self.search([])
        for slip in slip_ids:
            comparison_date = slip.date_from - timedelta(days=no_of_days)
            if today == comparison_date and slip.state == 'new':
                values = {
                    'state': 'to_pay',
                    'name': self.env['ir.sequence'].next_by_code('wk.fee.slip.sequence') or _('/'),
                }
                slip.write(values)
            elif slip.state == 'to_pay':
                mail_template = self.env.ref('wk_school_management.fee_slip_overdue_mail', raise_if_not_found=False)
                if mail_template:
                    mail_template.send_mail(slip.id)
                slip.state = 'overdue'

    def _get_default_payment_link_values(self):
        self.ensure_one()
        amount_max = self.total_amount
        amount = amount_max

        return {
            'currency_id': self.currency_id,
            'partner_id': self._get_fee_invoice_partner().id,
            'amount': amount,
            'amount_max': amount_max,
        }

    def action_view_invoice(self):
        self.ensure_one()
        description = f"Fee Slip:<strong> {self.name}</strong><br>" \
            f"Academic Year:<strong> {self.academic_year_id.name}</strong><br>" \
            f"Enrollment:<strong> {self.student_id.current_enrollment_id.name}</strong><br>" \
            f"Grade:<strong> {self.grade_id.name}</strong>"
        
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {
                'default_move_type': 'out_invoice',
                'default_partner_id': self._get_fee_invoice_partner().id,
                'default_invoice_date': date.today(),
                'default_state': 'draft',
                'default_narration': description,
                'default_invoice_line_ids': [],
                'default_fee_slip_id': self.id,
            }
        }

    @api.depends('state')
    def _compute_transaction_ids(self):
        for slip in self:
            if slip.state == 'paid':
                transaction = self.env['payment.transaction'].search([('fee_slip_ids', '=', slip.id)])
                slip.transaction_ids = transaction.ids
            else:
                slip.transaction_ids = False

    def preview_invoice(self):
        self.ensure_one()
        if len(self.invoice_ids) == 1:
            return {
                'type': 'ir.actions.act_url',
                'target': 'self',
                'url': self.invoice_ids[0].get_portal_url(),
            }
        return {
            'name': "Invoices",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': "{'move_type':'out_invoice'}",
        }

    def _create_invoices(self, final=False):
        description = f"Fee Slip:<strong> {self.name}</strong><br>" \
            f"Academic Year:<strong> {self.academic_year_id.name}</strong><br>" \
            f"Enrollment:<strong> {self.student_id.current_enrollment_id.name}</strong><br>" \
            f"Grade:<strong> {self.grade_id.name}</strong>"
        
        partner = self._get_fee_invoice_partner()
        if not partner:
            raise UserError(_(
                f"No customer contact found for student {self.student_id.name}."
            ))

        invoice_data = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': date.today(),
            'state': 'draft',
            'invoice_line_ids': [],
            'narration': description,
            'fee_slip_id': self.id,
        }

        for slip_line in self.fee_slip_line_ids:
            invoice_data['invoice_line_ids'].append((0, 0, {
                'product_id': slip_line.product_id.id,
                'price_unit': slip_line.fee,
            }))
        invoice = self.env['account.move'].sudo().create(invoice_data)
        self.invoice_ids = [(4, invoice.id)]
        return invoice
    
    def _get_fee_invoice_partner(self):
        self.ensure_one()
        student = self.student_id

        if student.partner_id:
            return student.partner_id

        if student.user_id:
            return student.user_id.partner_id

        parent_users = student.parent_ids.mapped('user_ids')
        if parent_users:
            return parent_users[0].partner_id
        return False

    def action_create_invoice(self):
        self.ensure_one()
        partner = self._get_fee_invoice_partner()
        invoice_lines = []
        for slip_line in self.fee_slip_line_ids:
            invoice_lines.append((0, 0, 
                {
                'product_id': slip_line.product_id.id,
                'price_unit': slip_line.fee,
                'name': slip_line.product_id.display_name,
            }))

        description = f"Fee Slip:<strong> {self.name}</strong><br>" \
            f"Academic Year:<strong> {self.academic_year_id.name}</strong><br>" \
            f"Enrollment:<strong> {self.student_id.current_enrollment_id.name}</strong><br>" \
            f"Grade:<strong> {self.grade_id.name}</strong>"

        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'views': [(self.env.ref('account.view_move_form').id, 'form')],
            'context': {
                'default_partner_id': partner.id,
                'default_currency_id': self.currency_id.id,
                'default_fee_slip_id': self.id,
                'default_move_type': 'out_invoice',
                'default_invoice_line_ids': invoice_lines,
                'default_narration': description,
            }
        }
        return action

    def action_view_payment_transactions(self):
        action = self.env['ir.actions.act_window']._for_xml_id('payment.action_payment_transaction')
        if len(self.transaction_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.transaction_ids.id
            action['views'] = []
        else:
            action['domain'] = [('id', 'in', self.transaction_ids.ids)]
        return action

    def get_payment_url(self):
        payment_url = self.get_base_url() + self._get_share_url(redirect=True)
        return payment_url


class FeeSlipLine(models.Model):

    _name = "wk.fee.slip.lines"
    _description = "Fee Slip Lines of Students"

    product_id = fields.Many2one(
        'product.product', string="Fee Element", required=True, domain="[('is_fee_element','=',True)]")
    fee = fields.Float(string="Fee", required=True, digits='Product Price')
    fee_slip_id = fields.Many2one('wk.fee.slip', string="Fee Slip")
