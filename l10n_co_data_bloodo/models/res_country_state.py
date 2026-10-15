# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCountryState(models.Model):
    _name = 'res.country.state'
    _inherit = ['res.country.state', 'mail.thread']

    dian_code = fields.Char('Código DIAN', tracking=True)
    name = fields.Char(tracking=True)
