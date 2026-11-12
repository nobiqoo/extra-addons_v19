# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    partner_required = fields.Boolean(
        string='Contact Required',
        help='Requires a contact on every journal item using this account '
             'before the journal entry can be posted.')
