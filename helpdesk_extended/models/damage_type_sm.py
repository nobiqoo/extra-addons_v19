# -*- coding: utf-8 -*-

from odoo import fields, models, _


class DamageTypeSm(models.Model):
    _name = 'damage.type.sm'
    _description = 'Damage type for helpdesk'

    name = fields.Char('Name')
    active = fields.Boolean('Active', default=True)
