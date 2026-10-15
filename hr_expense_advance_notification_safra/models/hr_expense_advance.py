# -*- coding: utf-8 -*-

from odoo import models


class HrExpenseAdvance(models.Model):
    _inherit = 'hr.expense.advance'

    def action_approved(self):
        res = super().action_approved()
        self._send_accounting_notification()
        return res

    def _send_accounting_notification(self):
        template = self.env.ref(
            'hr_expense_advance_notification_safra.mail_template_advance_approved_accounting',
            raise_if_not_found=False,
        )
        if not template:
            return

        group = self.env.ref(
            'hr_expense_advance_notification_safra.group_advance_accounting_notification',
            raise_if_not_found=False,
        )
        if not group:
            return

        partner_ids = group.sudo().users.partner_id.ids
        if not partner_ids:
            return

        template.send_mail_batch(
            self.ids,
            email_values={'recipient_ids': [(4, pid) for pid in partner_ids]},
        )
