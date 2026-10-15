# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountReconcileModel(models.Model):
    _inherit = 'account.reconcile.model'

    match_authorization_number = fields.Boolean(
        string='Match Authorization Number',
        help=(
            "If enabled, the automatic bank reconciliation will match a bank statement line "
            "with the customer payment or receipt voucher sharing the exact same Authorization "
            "Number, and reconcile them without any user intervention."
        ),
    )
