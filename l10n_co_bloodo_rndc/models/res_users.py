# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    rndc_user = fields.Char('RNDC Usuario')
    rndc_pwd = fields.Char('RNDC Clave')