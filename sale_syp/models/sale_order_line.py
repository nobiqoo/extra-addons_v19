# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'

    purchase_margin = fields.Float(
        "Purchase Margin", compute='_compute_margin_by_supplier',
        digits='Product Price', store=True, groups="base.group_user", precompute=True)
    purchase_margin_percent = fields.Float(
        " Purchase Margin (%)", compute='_compute_margin_by_supplier', store=True, groups="base.group_user", precompute=True)
    purchase_price_by_supplier = fields.Float(
        string="Purchase Cost", compute="_compute_purchase_price_by_supplier",
        digits='Product Price', store=True, readonly=False, copy=False, precompute=True,
        groups="base.group_user")

    @api.depends('product_id', 'order_id.partner_id', 'company_id', 'currency_id', 'product_uom_id')
    def _compute_purchase_price_by_supplier(self):
        for line in self:
            if not line.product_id:
                line.purchase_price_by_supplier = 0.0
                continue

            line = line.with_company(line.company_id)

            supplier_info = line.product_id.seller_ids

            if supplier_info:

                supplier_price = supplier_info[0].price
                supp_uom = supplier_info[0].product_uom
                if supp_uom and supp_uom != line.product_uom_id:
                    supplier_price = supp_uom._compute_price(supplier_price, line.product_uom_id)
                src_currency = supplier_info[0].currency_id or line.company_id.currency_id
                purchase_price = line._convert_to_sol_currency(supplier_price, src_currency)
                line.purchase_price_by_supplier = purchase_price
            else:

                line.purchase_price_by_supplier = 0.0

    @api.depends('price_subtotal', 'product_uom_qty', 'purchase_price', 'purchase_price_by_supplier')
    def _compute_margin_by_supplier(self):
        for line in self:
            line.purchase_margin = line.price_subtotal - (line.purchase_price_by_supplier * line.product_uom_qty)
            line.purchase_margin_percent = line.price_subtotal and line.purchase_margin/line.price_subtotal

    @api.onchange('purchase_price_by_supplier')
    def _onchange_purchase_price_unit(self):
        for line in self:
            if line.purchase_price_by_supplier and line.pricelist_item_id:
                line.price_unit = line.purchase_price_by_supplier * (1 - line.pricelist_item_id.price_discount/100)