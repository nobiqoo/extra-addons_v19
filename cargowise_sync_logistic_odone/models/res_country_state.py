# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    code_cw = fields.Char('Código CW')
