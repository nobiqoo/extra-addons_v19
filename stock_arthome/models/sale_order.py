# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_comment = fields.Text(
        string='Dispatch Note/Instruction',
        copy=False,
        tracking=True,
        help='Dispatch instructions written once in the order. They are copied to its transfers (pick, pack and '
             'delivery) and printed on their reports, and copied to the invoice when it is created. Editing them '
             'updates only the open transfers.',
    )

    box_count = fields.Integer(
        string='Box Count',
        compute='_compute_box_count',
        store=True,
        help='Sum of the box count of the deliveries and dropships of the order that are not cancelled.',
    )

    @api.depends('picking_ids.box_count', 'picking_ids.state', 'picking_ids.picking_type_id')
    def _compute_box_count(self):
        """Suma las cajas de las entregas y dropship no canceladas del pedido."""
        boxes = defaultdict(int)
        order_ids = self._origin.ids
        if order_ids:
            boxes.update(self.env['stock.picking']._read_group(
                [('sale_id', 'in', order_ids), ('state', '!=', 'cancel'),
                 ('picking_type_code', 'in', ('outgoing', 'dropship'))],
                ['sale_id'],
                ['box_count:sum'],
            ))
        for order in self:
            order.box_count = boxes[order._origin]

    def write(self, vals):
        if 'delivery_comment' not in vals:
            return super().write(vals)
        previous_comments = {
            order.id: order.delivery_comment
            for order in self
            if (order.delivery_comment or '') != (vals['delivery_comment'] or '')
        }
        res = super().write(vals)
        if previous_comments:
            self.env['stock.picking']._propagate_delivery_comment('sale_id', previous_comments, vals['delivery_comment'])
        return res

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals['delivery_comment'] = self.delivery_comment
        return invoice_vals

    def _create_invoices(self, grouped=False, final=False, date=None):
        """Une los comentarios distintos de los pedidos cuando una factura agrupa varios."""
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        for move in moves:
            orders = move.line_ids.sale_line_ids.order_id
            if len(orders) < 2:
                continue
            comments = list(dict.fromkeys(comment for comment in orders.sorted('id').mapped('delivery_comment') if comment))
            move.delivery_comment = '\n'.join(comments) or False
        return moves
