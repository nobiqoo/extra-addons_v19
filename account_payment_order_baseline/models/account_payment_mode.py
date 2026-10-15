# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountPaymentMode(models.Model):

    _inherit = "account.payment.mode"

    combined_move_account_payment_order = fields.Boolean(
        string='Combined Move on Payment Order', default=False)
