# -*- coding: utf-8 -*-

from odoo import api, models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    apply_product_reference = fields.Boolean(
        string="Automatic code", default=False)
