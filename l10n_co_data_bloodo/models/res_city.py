# -*- coding: utf-8 -*-

from odoo import fields, models


class City(models.Model):
    _name = 'res.city'
    _inherit = ['res.city', 'mail.thread']

    dian_code = fields.Char('Código DIAN', tracking=True)
    name = fields.Char(tracking=True)
    active = fields.Boolean('Activo',
                            default=True,
                            tracking=True)
