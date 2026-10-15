# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountVoucher(models.Model):
    _inherit = "account.voucher"

    check_number = fields.Char(
        string='N° de Cheque',
    )
