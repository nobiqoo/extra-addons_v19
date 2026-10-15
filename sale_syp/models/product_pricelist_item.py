# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PricelistItemInherit(models.Model):
    _inherit = 'product.pricelist.item'

    base = fields.Selection(
        selection_add=[('supplier_list_price', 'Supplier List Price')],
        ondelete={'supplier_list_price': 'set default'}
    )

    def _compute_base_price(self, product, quantity, uom, date, currency, **kwargs):
        """ Compute the base price for a given rule

        :param product: recordset of product (product.product/product.template)
        :param float quantity: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency conversions
        :param currency: pricelist currency

        :returns: base price, expressed in provided pricelist currency
        :rtype: float
        """
        rule_base = self.base or 'list_price'

        if rule_base != 'supplier_list_price':
            return super()._compute_base_price(product, quantity, uom, date, currency, **kwargs)

        currency.ensure_one()
        supplier_info = product._select_seller(
            partner_id=None,
            quantity=quantity,
            date=date,
            uom_id=uom
        )
        if supplier_info:
            price_unit = supplier_info.price
            supp_uom = supplier_info.product_uom
            if supp_uom and supp_uom != uom:
                price_unit = supp_uom._compute_price(price_unit, uom)
            src_currency = supplier_info.currency_id or self.env.company.currency_id
            price = price_unit
        else:
            raise ValidationError(
                _('No supplier price found for the product. Please provide a supplier price.'))

        if src_currency != currency:
            price = src_currency._convert(
                price, currency, self.env.company, date, round=False)

        return price
