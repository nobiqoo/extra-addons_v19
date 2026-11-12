# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    income_currency_exchange_account_made_id = fields.Many2one(
        comodel_name='account.account',
        string="Realized exchange gain account",
        help="Account used for the manual 'difference in change' entries "
             "(Accounting > Realizar diferencia en cambio), kept separate "
             "from the account used by Odoo's automatic exchange difference "
             "entries.",
    )
    expense_currency_exchange_account_made_id = fields.Many2one(
        comodel_name='account.account',
        string="Realized exchange loss account",
        help="Account used for the manual 'difference in change' entries "
             "(Accounting > Realizar diferencia en cambio), kept separate "
             "from the account used by Odoo's automatic exchange difference "
             "entries.",
    )
