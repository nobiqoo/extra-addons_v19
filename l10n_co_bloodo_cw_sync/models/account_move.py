# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, tools, Command, _
from datetime import datetime
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    observaciones_1 = fields.Text('Observaciones')

    def _notizen_mitbringen(self):
        res = super()._notizen_mitbringen()
        if self.observaciones_1:
            res.append(self.observaciones_1[:500])
        return res

    # def action_send_mail(self):
    #     _logger.error("[PEEK-ABC] Start action_send_mail %s" % datetime.now())
    #     param = self.env['ir.config_parameter'].sudo().get_param(
    #         'l10n_co_bloodo.type_send_ei_mail', 'once_cc')
    #     msg = _('Su factura no ha sido validada.')
    #     if not self.name:
    #         raise UserError(msg)
    #     template_id = self.env.ref('l10n_co_bloodo.dian_email_template')
    #     zip_attachment = False
    #     pse_instructive = False
    #     if self.env.company.pse_file_instructive:
    #         pse_instructive = self.env['ir.attachment'].create({
    #             'name': 'Instructivo de Pago.pdf',
    #             'type': 'binary',
    #             'datas': self.env.company.pse_file_instructive
    #         })
    #     if self.fe_zip_file:
    #         zip_attachment = self.env['ir.attachment'].create({
    #             'name': self.fe_zip_fname,
    #             'type': 'binary',
    #             'datas': self.fe_zip_file
    #         })
    #     if param == 'once_cc':
    #         email_to_vals = template_id._render_field(
    #             'email_to', self.ids)[self.id]
    #         email_to = tools.email_split(email_to_vals)
    #         partner_obj = self.env['res.partner']
    #         partner_ids = []
    #         for mail in email_to:
    #             partner = partner_obj.find_or_create(mail)
    #             partner_ids.append(partner.id)
    #         email_vals = {
    #             'is_notification': True,
    #         }
    #         if partner_ids:
    #             email_vals['email_to'] = False
    #             email_vals['recipient_ids'] = [
    #                 Command.link(pid) for pid in partner_ids]
    #         if zip_attachment:
    #             email_vals['attachment_ids'] = [(4, zip_attachment.id, 0)]
    #         if pse_instructive and email_vals.get('attachment_ids'):
    #             email_vals['attachment_ids'] += [(4, pse_instructive.id, 0)]
    #         elif pse_instructive:
    #             email_vals['attachment_ids'] = [(4, pse_instructive.id, 0)]
    #         force_send = self._context.get('eimail_force', False)
    #         template_id.send_mail(self.id, force_send=force_send, email_values=email_vals,
    #                               email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature')
    #     else:
    #         if zip_attachment:
    #             template_id.attachment_ids = [(4, zip_attachment.id, 0)]
    #         if pse_instructive and template_id.attachment_ids:
    #             template_id.attachment_ids += [(4, pse_instructive.id, 0)]
    #         elif pse_instructive:
    #             template_id.attachment_ids = [(4, pse_instructive.id, 0)]
    #         kwargs = {
    #             'notify': False
    #         }
    #         self.with_context(no_new_invoice=True).message_post_with_template(
    #             template_id.id,
    #             email_layout_xmlid='mail.mail_notification_paynow',
    #             **kwargs)
    #         if zip_attachment:
    #             template_id.attachment_ids = [
    #                 (3, z, 0) for z in zip_attachment.ids]
    #     self.write({'mail_sent': True})
    #     _logger.error("[PEEK-ABC] End action_send_mail %s" % datetime.now())
    #     return True
