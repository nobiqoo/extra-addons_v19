# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # consol
    list_price_base = fields.Float(string='Price base', default=1.0)
    points_to_add = fields.Float(string='Price extra', default=0.0)
    list_price = fields.Float(compute='compute_list_price',
                              readonly=True,
                              store=True)
    sale_currency_id = fields.Many2one(comodel_name='res.currency',
                                       string='Sale currency')

    @api.depends('list_price_base', 'points_to_add', 'sale_currency_id')
    def compute_list_price(self):
        usd_currency = self.env.ref('base.USD')
        company = self.env.company
        now = datetime.now()
        for record in self:
            price = record.list_price_base + record.points_to_add
            record.list_price = record.sale_currency_id._convert(
                price, usd_currency, company, now)
