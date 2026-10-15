# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    purchase_margin = fields.Monetary("Margin", compute='_compute_margin_purchase', store=True)
    purchase_margin_percent = fields.Float("Margin (%)", compute='_compute_margin_purchase', store=True, aggregator="avg")

    @api.depends('order_line.purchase_margin', 'amount_untaxed')
    def _compute_margin_purchase(self):
        if not all(self._ids):
            for order in self:
                order.purchase_margin = sum(order.order_line.mapped('purchase_margin'))
                order.purchase_margin_percent = order.amount_untaxed and order.purchase_margin/order.amount_untaxed
        else:
            # On batch records recomputation (e.g. at install), compute the margins
            # with a single read_group query for better performance.
            # This isn't done in an onchange environment because (part of) the data
            # may not be stored in database (new records or unsaved modifications).
            grouped_order_lines_data = self.env['sale.order.line']._read_group(
                [
                    ('order_id', 'in', self.ids),
                ], ['order_id'], ['purchase_margin:sum'])
            mapped_data = {order.id: margin for order, margin in grouped_order_lines_data}
            for order in self:
                order.purchase_margin = mapped_data.get(order.id, 0.0)
                order.purchase_margin_percent = order.amount_untaxed and order.purchase_margin/order.amount_untaxed
