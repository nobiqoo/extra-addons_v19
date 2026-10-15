# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    ldp_price = fields.Float('Sale price ldP',
                             compute='_compute_ldp_price',
                             digits='Product Price',
                             help="Sales price according to price list selected in company configuration.")

    def _compute_ldp_price(self):
        for product in self:
            company = self.env.company
            domain = []
            if company.show_price_variant_ldp:
                domain.append(
                    ('pricelist_id', '=', company.show_price_variant_ldp.id))
            domain += [
                ('pricelist_id.active', '=', True),
                '|',
                '&', ('product_tmpl_id', '=',
                      product.product_tmpl_id.id), ('applied_on', '=', '1_product'),
                '&', ('product_id', '=', product.id), ('applied_on',
                                                       '=', '0_product_variant'),
            ]
            pricelist_item = self.env['product.pricelist.item'].search(
                domain, order='id')
            product.ldp_price = pricelist_item and pricelist_item[0].fixed_price or 0
