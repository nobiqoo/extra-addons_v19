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
from markupsafe import Markup
from odoo.exceptions import UserError
from datetime import datetime

_logger = logging.getLogger(__name__)


class CancelReason(models.TransientModel):

    _name = 'cancel.reset.reason'
    _description = 'reason for application cancel and reset'

    reason = fields.Text(string="Reason", required=True)

    def reason_application_cancel_reset(self):
        self.ensure_one()
        active_ids = self.env.context.get('active_ids')
        records = self.env['wk.application.form'].browse(active_ids)
        button_name = self.env.context.get("default_name")

        for record in records:
            if button_name == 'cancel':
                if record.state == 'new' or record.state == 'confirm':
                    ctx = {'reason': self.reason}
                    mail_template = self.env.ref(
                        'wk_school_management.application_cancelling_mail')
                    if mail_template:
                        mail_template.with_context(ctx).send_mail(record.id)
                    record.state = 'cancel'
                else:
                    raise UserError(
                        _("Application only in new or confirm stage can be marked as cancel."))

            elif button_name == 'reset':
                if record.state != 'new':
                    body = Markup(
                        _("Reason for Reset :- <strong> %s</strong>", self.reason))
                    record.message_post(body=body)
                    record.state = 'new'
                else:
                    raise UserError(
                        _("This application already seems to be in the new state"))
        return True
    
    def reason_enrollment_cancel_reset(self):
        self.ensure_one()
        active_id = self.env.context.get('active_id')
        record = self.env['student.enrollment'].browse(active_id)
        body = Markup(
            _("Reason for Cancellation :- <strong> %s</strong>", self.reason))
        record.message_post(body=body)
        record.state = 'cancel'


class ScholarshipProductDisplay(models.TransientModel):

    _name = 'wk.scholarship.update.wizard'
    _description = 'Used for displaying and updating scholarships to paid'

    scholarship_ids = fields.Many2many('wk.student.scholarship', string="Scholarship")

    def mark_paid(self):
        scholarship_ids = self.env.context.get("default_scholarship_ids")
        scholarships = self.env['wk.student.scholarship'].browse(scholarship_ids)

        for scholarship in scholarships:
            if scholarship.invoice_status == 'paid':
                scholarship.state = 'paid'
                scholarship.paid_date = fields.Date.today()


class MessageDisplayWizard(models.TransientModel):

    _name = 'wk.message.wizard'
    _description = 'Used for displaying message'

    message = fields.Char(string='Message')
    note  = fields.Html(string='Note')

    def _revoke_portal_access_if_exists(self, partner):
        """Revoke portal access if the partner has it."""
        if not partner:
            return
        has_portal_access = any(
            user.has_group('base.group_portal') for user in partner.user_ids
        )
        if has_portal_access:
            portal_wizard = self.env['portal.wizard'].with_context(default_partner_ids=[partner.id]).create({})
            wizard_user = self.env['portal.wizard.user'].create({
                'wizard_id': portal_wizard.id,
                'partner_id': partner.id,
                'email': partner.email,
            })
            wizard_user.action_revoke_access()

    def revoke_student_portal_access(self):
        active_ids = self.env.context.get('active_ids', [])
        student_records = self.env['student.student'].browse(active_ids)

        for student in student_records:
            if student.partner_id:
                self._revoke_portal_access_if_exists(student.partner_id)

            student.active = False

            for parent in student.parent_ids:
                if parent.student_portal_active:
                    active_students = self.env['student.student'].search([
                        ('parent_ids', 'in', parent.id),
                        ('active', '=', True)
                    ])
                    if len(active_students) <= 1:
                        self._revoke_portal_access_if_exists(parent)
                        parent.active = False
            student._compute_parent_portal_active()
        message = _(
            "Access for this student and their linked parent(s), if applicable, has been revoked."
        )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Revoke User Access',
            'res_model': 'wk.message.wizard',
            'views': [(self.env.ref('wk_school_management.wk_message_wizard_view_form_success').id, 'form')],
            'target': 'new',
            'context': {
                'default_message': message
            }
        }
    
    def wk_remark_button(self):
        request_book = self.env['wk.book.history'].browse(self._context.get('active_ids'))
        if request_book.copy_book_sr_id:
            request_book.copy_book_sr_id.state = 'available'
            if self._context['return_date'] == 'use_return_date':
                request_book.write({'state':'return','return_to_id':self._uid,'remark':self.message})
            elif self._context['return_date'] == 'default_date':
                request_book.write({'return_date':datetime.now(), 'state': 'return', 'return_to_id' : self._uid, 'remark' : self.message})
            else:
                raise UserError(_("System internal error please contact us"))
            request_book.calculate_fine()
        else:
            raise UserError(_("This serial number is not available"))
        return True
    
    def fine_collected(self):
        for rec in self:
            fine = self.env.context.get('fine', False)
            if fine:
                fine_rec = self.env['book.library.fine'].sudo().browse(fine)
                if fine_rec:
                    fine_rec.status = 'collected'

