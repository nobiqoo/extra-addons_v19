# -*- coding: utf-8 -*-

from email.policy import default
from odoo import fields, models, _


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    invoice_number = fields.Char('Invoice number')
    is_repair = fields.Boolean('Repair', default=False)
    technician_notes = fields.Html('Technician notes')
    payment_support = fields.Binary('Payment support')
    payment_support_fname = fields.Char('File name payment support')
    is_warranty = fields.Boolean('Warranty', default=False)
    state = fields.Selection(
        selection_add=[('denied', 'Denied')],
        help="* The \'Draft\' status is used when a user is encoding a new and unconfirmed repair order.\n"
             "* The \'Confirmed\' status is used when a user confirms the repair order.\n"
             "* The \'Ready to Repair\' status is used to start to repairing, user can start repairing only after repair order is confirmed.\n"
             "* The \'Under Repair\' status is used when the repair is ongoing.\n"
             "* The \'To be Invoiced\' status is used to generate the invoice before or after repairing done.\n"
             "* The \'Done\' status is set when repairing is completed.\n"
             "* The \'Denied\' status is used when a user want to send the denial letter.\n"
             "* The \'Cancelled\' status is used when user cancel repair order."
    )

    def action_send_mail_denied(self):
        self.ensure_one()
        template_id = self.env.ref(
            'helpdesk_extended.mail_template_repair_denial_letter').id
        ctx = {
            'default_model': 'repair.order',
            'default_res_ids': self.ids,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'custom_layout': 'mail.mail_notification_light',
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': ctx,
        }

    def state_to_denied(self):
        self.write({
            'state': 'denied',
        })
