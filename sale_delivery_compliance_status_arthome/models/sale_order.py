# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_compliance_status = fields.Selection(
        selection=[
            ('pending', "Pending"),
            ('partial', "Partial"),
            ('full', "Fully Delivered"),
            ('short', "Under-Delivered"),
            ('excess', "Over-Delivered"),
        ],
        string="Delivery Compliance Status",
        compute='_compute_delivery_compliance_status',
        store=True,
        help="Blue: Pending/Partial\nGreen: Fully Delivered\nRed: Under-Delivered\nOrange: Over-Delivered",
    )

    @api.depends(
        'state',
        'picking_ids.state',
        'order_line.qty_delivered_method',
        'order_line.qty_delivered',
        'order_line.product_uom_qty',
    )
    def _compute_delivery_compliance_status(self):
        """Agrega cantidades y estado de las entregas para derivar el cumplimiento de despacho."""
        confirmed_orders = self.filtered(lambda so: so.state == 'sale')
        (self - confirmed_orders).delivery_compliance_status = False
        if not confirmed_orders:
            return

        picking_states = defaultdict(set)
        for order, state in self.env['stock.picking']._read_group(
            [('sale_id', 'in', confirmed_orders.ids)],
            ['sale_id', 'state'],
        ):
            picking_states[order.id].add(state)

        qty_by_order = {
            order.id: (ordered_qty, delivered_qty)
            for order, ordered_qty, delivered_qty in self.env['sale.order.line']._read_group(
                [
                    ('order_id', 'in', confirmed_orders.ids),
                    ('qty_delivered_method', '=', 'stock_move'),
                ],
                ['order_id'],
                ['product_uom_qty:sum', 'qty_delivered:sum'],
            )
        }

        precision = self.env['decimal.precision'].precision_get('Product Unit')
        for order in confirmed_orders:
            if order.id not in qty_by_order:
                # Sin lineas con entrega fisica: el estado no aplica.
                order.delivery_compliance_status = False
                continue
            ordered_qty, delivered_qty = qty_by_order[order.id]
            open_states = picking_states.get(order.id, set()) - {'done', 'cancel'}
            if open_states:
                # Aun queda una Orden de Entrega sin cerrar (incluye backorders pendientes).
                order.delivery_compliance_status = 'partial' if delivered_qty else 'pending'
            elif 'done' not in picking_states.get(order.id, set()):
                order.delivery_compliance_status = 'pending'
            else:
                qty_comparison = float_compare(delivered_qty, ordered_qty, precision_digits=precision)
                if qty_comparison == 0:
                    order.delivery_compliance_status = 'full'
                elif qty_comparison > 0:
                    order.delivery_compliance_status = 'excess'
                else:
                    order.delivery_compliance_status = 'short'
