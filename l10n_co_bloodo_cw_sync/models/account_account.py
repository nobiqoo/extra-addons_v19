# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountAccount(models.Model):
    _inherit = 'account.account'

    tercero = fields.Boolean("Ingreso a terceros", default=False)
