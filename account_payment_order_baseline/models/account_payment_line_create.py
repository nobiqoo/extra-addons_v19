# -*- coding: utf-8 -*-

from odoo import models


class AccountPaymentLineCreate(models.TransientModel):
    _inherit = "account.payment.line.create"

    def create_payment_lines(self):
        if self.move_line_ids:
            self.move_line_ids.create_payment_line_from_move_line(
                self.order_id)
        self.order_id._onchange_payment_line_ids()
        return True
