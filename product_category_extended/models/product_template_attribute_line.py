# -*- coding: utf-8 -*-

from odoo import models, api


class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    @api.onchange('attribute_id')
    def _onchange_attribute_id(self):
        already_set = []
        for line in self.product_tmpl_id.attribute_line_ids:
            already_set.append(line.attribute_id.id)
        default_attribute = self.env['product.attribute'].search(
            [('id', 'not in', already_set)], limit=1, order='name asc')
        self.attribute_id = default_attribute
        self.value_ids = self.value_ids.filtered(
            lambda pav: pav.attribute_id == self.attribute_id)
