# -*- coding: utf-8 -*-

from collections import defaultdict
from odoo import api,models,fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    city_id = fields.Many2one(
        'res.city',
        string="Ciudad",
        help="Ciudad relacionada con esta línea de pedido."
    )

    # @api.onchange(
    #     'price_subtotal',
    # )
    # def _onchange_base_tax(self):
    #     self.order_id.calculate_base()

    def compute_line_tax(self):
        tax_ids = self.env['account.tax']

        taxes_by_product_company = defaultdict(lambda: self.env['account.tax'])
        lines_by_company = defaultdict(lambda: self.env['sale.order.line'])
        cached_taxes = {}
        for line in self:
            lines_by_company[line.company_id] += line
        for product in self.product_id:
            for tax in product.taxes_id:
                taxes_by_product_company[(product, tax.company_id)] += tax
        for company, lines in lines_by_company.items():
            for line in lines.with_company(company):
                taxes = taxes_by_product_company[(line.product_id, company)]
                if not line.product_id or not taxes:
                    # Nothing to map
                    line.tax_ids = False
                    continue
                fiscal_position = line.order_id.fiscal_position_id
                cache_key = (fiscal_position.id, company.id, tuple(taxes.ids))
                cache_key += line._get_custom_compute_tax_cache_key()
                if cache_key in cached_taxes:
                    result = cached_taxes[cache_key]
                else:
                    result = fiscal_position.map_tax(taxes)
                    cached_taxes[cache_key] = result
                # If company_id is set, always filter taxes by the company
                tax_ids |= result

        return tax_ids
    
    @api.onchange('city_id', 'price_subtotal')
    def _onchange_city_or_subtotal(self):
        order = self.order_id
        if order and not order.company_id.calculate_ica_by_line:
            return 

        if not self.city_id:
            return

        Tax = self.env['account.tax']
        taxes = Tax
        taxes |= self.compute_line_tax()

        applicable_taxes = taxes.calculate_base_single_line(
            line=self,
            city_id=self.city_id,
            partner_id=self.order_id.partner_id,
        )

        if applicable_taxes:
            self.tax_ids = applicable_taxes  

    @api.onchange('product_id')
    def _onchange_city_id(self):
        self.city_id = self.order_id.city_id
