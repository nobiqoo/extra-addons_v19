# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CertificateReportSendMail(models.TransientModel):
    _name = "certificate.report.send.mail"
    _description = "Send mails Wizard"

    def send_mails(self):
        reports = self.env['withholding.certificate.report'].search(
            [('id', 'in', self._context.get('active_ids', []))])
        if not reports:
            raise ValidationError(_('There are no reports to send.'))
        for report in reports:
            report.send_email()
        return {'type': 'ir.actions.act_window_close'}
