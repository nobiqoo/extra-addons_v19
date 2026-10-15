# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    @api.constrains('split_transactions', 'journal_id')
    def _check_split_transactions_for_authorization_number(self):
        for method in self:
            if method.type == 'bank' and not method.split_transactions:
                raise ValidationError(_(
                    "Please enable \"Identify Customer\" on the payment method \"%(method)s\". "
                    "Non-cash payment methods must keep a separate journal entry per transaction "
                    "so each one can carry its own Authorization Number and be reconciled "
                    "individually against the bank statement.",
                    method=method.name,
                ))
