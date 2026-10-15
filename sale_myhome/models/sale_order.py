# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    purchase_order_names = fields.Char(
        string='OC Relacionadas',
        compute='_compute_purchase_order_names',
        store=False,
    )
    tracking_number = fields.Char(
        string='Número de Guía',
        help='Número de guía que se propagará al picking de entrega',
        tracking=True
    )

    def _get_purchase_orders(self):
        self.ensure_one()
        return self.order_line.purchase_line_ids.order_id

    @api.depends('order_line.purchase_line_ids.order_id')
    def _compute_purchase_order_names(self):
        for order in self:
            pos = order._get_purchase_orders()
            order.purchase_order_names = ', '.join(pos.mapped('name')) \
                if pos else ''


    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order.tracking_number:
                pickings = order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing'
                    and p.state not in ('done', 'cancel')
                )
                if pickings:
                    pickings.write({'tracking_number': order.tracking_number})

        return res

    def write(self, vals):
        res = super().write(vals)
        if 'tracking_number' in vals:
            for order in self:
                pickings = order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing'
                    and p.state not in ('done', 'cancel')
                )
                if pickings:
                    pickings.write({'tracking_number': vals['tracking_number']})
        return res