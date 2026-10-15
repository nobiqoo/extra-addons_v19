# -*- coding: utf-8 -*-

import itertools
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.attribute.value'

    number = fields.Char(string="Number")
    secondary_value = fields.Many2one(
        'product.attribute.value', string="Secondary value")
