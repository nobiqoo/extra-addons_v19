# -*- coding: utf-8 -*-

from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _create_order_picking(self):
        res = super()._create_order_picking()
        if self.general_customer_note:
            self.picking_ids.filtered(lambda picking: not picking.delivery_comment).delivery_comment = self.general_customer_note
        return res

    def write(self, vals):
        if 'general_customer_note' not in vals:
            return super().write(vals)
        previous_comments = {
            order.id: order.general_customer_note
            for order in self
            if (order.general_customer_note or '') != (vals['general_customer_note'] or '')
        }
        res = super().write(vals)
        if previous_comments:
            self.env['stock.picking']._propagate_delivery_comment(
                'pos_order_id', previous_comments, vals['general_customer_note'])
        return res
