# -*- coding: utf-8 -*-
from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _get_split_account_payment_vals(self, payment, amounts, accounting_partner, destination_account):
        # EXTENDS point_of_sale
        vals = super()._get_split_account_payment_vals(payment, amounts, accounting_partner, destination_account)
        vals['authorization_number'] = payment.authorization_number
        return vals
