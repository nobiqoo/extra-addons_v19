# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _


class Productproduct(models.Model):
    _inherit = 'product.product'

    invima = fields.Char(
        'INVIMA', help='INVIMA number of the product', default='')
    invima_expiration_date = fields.Date(
        'INVIMA Expiration Date', help='INVIMA expiration date of the product')
    witness = fields.Text(
        'Witness', help='Witness of the product', compute='_compute_witness')

    @api.depends('invima', 'name')
    def _compute_witness(self):
        for product in self:
            product.witness = _(f'''Importador:
        {product.env.company.display_name}
        {product.env.company.street} - {product.env.company.city_id.display_name}
        INVIMA: {product.invima}
        [{product.default_code}] {product.name}''')
