# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    delivery_comment = fields.Text(
        string='Dispatch Note/Instruction',
        copy=False,
        help='Dispatch instructions copied from the sale order when the invoice was created.',
    )
