# -*- coding: utf-8 -*-
from odoo import fields, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    authorization_number = fields.Char(
        string='Authorization Number',
        help=(
            "Bank authorization or approval number for this Point of Sale payment (card, bank "
            "transfer, etc.). It is propagated to the resulting accounting entry so it can be "
            "used to automatically match it with the corresponding bank statement line."
        ),
    )
