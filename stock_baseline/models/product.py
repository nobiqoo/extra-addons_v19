# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_group_user = fields.Boolean(
        string='Es grupo de usuario', compute="_compute_group_user_type", default=False)
    is_group_manager = fields.Boolean(
        string='Es grupo de gerente', compute="_compute_group_user_type", default=False)

    def _compute_group_user_type(self):
        for record in self:
            record.is_group_user = self.env.user.has_group(
                'stock_baseline.group_user_hide_standard_price')
            record.is_group_manager = self.env.user.has_group(
                'stock_baseline.group_hide_standard_price')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_group_user = fields.Boolean(
        related='product_tmpl_id.is_group_user')
    is_group_manager = fields.Boolean(
        related='product_tmpl_id.is_group_manager')
