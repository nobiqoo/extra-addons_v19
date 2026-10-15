# -*- encoding: utf-8 -*-

from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = "product.template"

    origin_fel = fields.Char('Origen')
