# -*- coding: utf-8 -*-
from odoo import fields, models

class AccountAccount(models.Model):
    _inherit = 'account.account'

    balance_of_the_day = fields.Float(string='Balance of the day')