# -*- coding: utf-8 -*-

from odoo import api, models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    reference = fields.Char(string="Reference")
