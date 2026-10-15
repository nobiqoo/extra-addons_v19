# -*- coding: utf-8 -*-

from odoo import api, models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    is_kit = fields.Boolean(string="Is Kit", default=False)

