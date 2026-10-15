# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # consol
    city = fields.Char(string='City.')
    code = fields.Char(string='Code')
    position = fields.Char(string='Position')