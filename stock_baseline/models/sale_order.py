# -*- coding: utf-8 -*-

from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_procurement_group_vals(self):
        vals = super(SaleOrderLine, self)._prepare_procurement_group_vals()
        vals.update(
            {'analytic_account_id': self.order_id.analytic_account_id.id})
        return vals
