# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _, SUPERUSER_ID
import logging
import base64

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    fee_slip_ids = fields.Many2many('wk.fee.slip', string='Fee Slips', copy=False, readonly=True)
    fee_slip_ids_nbr = fields.Integer(compute='_compute_fee_slip_ids_nbr', string='# of Fee Slips')

    @api.depends('fee_slip_ids')
    def _compute_fee_slip_ids_nbr(self):
        for trans in self:
            trans.fee_slip_ids_nbr = len(trans.fee_slip_ids)

    def _log_message_on_linked_documents(self, message):
        author = self.env.user.partner_id if self.env.uid == SUPERUSER_ID else self.partner_id
        if self.source_transaction_id:
            for invoice in self.source_transaction_id.invoice_ids:
                invoice.message_post(body=message, author_id=author.id)
            payment_id = self.source_transaction_id.payment_id
            if payment_id:
                payment_id.message_post(body=message, author_id=author.id)
        for slip in self.fee_slip_ids or self.source_transaction_id.fee_slip_ids:
            slip.message_post(body=message, author_id=author.id)

    def _post_process(self):
        res = super()._post_process()
        for tx in self:
            invoices = tx.invoice_ids
            if not invoices:
                continue
            slips = invoices.mapped('fee_slip_id')

            for slip in slips:
                paid_invoices = invoices.filtered(lambda inv: inv.fee_slip_id.id == slip.id)
                for inv in paid_invoices:
                    if inv.state != 'posted':
                        inv.action_post()
                    inv.payment_state = 'paid' if inv.amount_residual == 0 else 'partial'

                all_invoices = slip.invoice_ids.filtered(lambda inv: inv.state == 'posted')

                total_amount = sum(all_invoices.mapped('amount_total'))
                total_residual = sum(all_invoices.mapped('amount_residual'))
                total_paid = total_amount - total_residual

                if total_paid >= slip.total_amount:
                    slip.state = 'paid'
                elif total_paid > 0:
                    slip.state = 'partial'
                else:
                    slip.state = slip.state
                mail_template = self.env.ref('wk_school_management.fee_slip_success_mail', raise_if_not_found=False)
                if mail_template:
                    attachments = []
                    for inv in paid_invoices:
                        pdf_data = self.env['ir.actions.report'] \
                            .with_context(force_report_rendering=True) \
                            ._render('account.account_invoices', inv.id)[0]
                        attachment = self.env['ir.attachment'].create({
                            'name': f"Invoice_{inv.name}.pdf",
                            'type': 'binary',
                            'datas': base64.b64encode(pdf_data),
                            'res_model': 'wk.fee.slip',
                            'res_id': slip.id,
                            'mimetype': 'application/pdf',
                        })
                        attachments.append(attachment.id)

                    mail_template.attachment_ids = [(6, 0, attachments)]
                    subject = "Fee Slip Fully Paid" if slip.state == 'paid' else "Fee Slip Payment Update (Partial Payment)"
                    mail_template = mail_template.with_context(custom_subject=subject)
                    mail_template.send_mail(slip.id)
        return res


    def action_view_fee_slip(self):
        action = {
            'name': _('Fee Slip(s)'),
            'type': 'ir.actions.act_window',
            'res_model': 'wk.fee.slip',
            'target': 'current',
        }
        fee_slip_ids = self.fee_slip_ids.ids
        if len(fee_slip_ids) == 1:
            action['res_id'] = fee_slip_ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', fee_slip_ids)]
        return action
