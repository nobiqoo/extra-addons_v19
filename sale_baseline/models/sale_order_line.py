# -*- coding: utf-8 -*-

from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    check_user_edit_line = fields.Boolean()
    shipping_cost = fields.Float(string='Shipping Cost', default=0.0)

    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line(
            **optional_values)
        res['shipping_cost'] = self.shipping_cost
        return res
