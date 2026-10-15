# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line'

    purchase_order_line_ids = fields.One2many(
        'purchase.order.line', 'approval_line_id',
        string='Líneas de compra', copy=False)

    qty_purchased = fields.Float(
        string='Cantidad Gestionada (Comprada)',
        compute='_compute_qtys',
        store=True,
        compute_sudo=True,
        digits='Product Unit of Measure')

    supplied_qty = fields.Float(
        string='Cantidad Abastecida',
        compute='_compute_qtys',
        store=True,
        compute_sudo=True,
        digits='Product Unit of Measure')

    qty_pending_to_buy = fields.Float(
        string='Pendiente por comprar',
        compute='_compute_qtys',
        store=True,
        compute_sudo=True,
        digits='Product Unit of Measure')

    @api.depends(
        'quantity', 'product_uom_id',
        'purchase_order_line_ids.product_qty',
        'purchase_order_line_ids.product_uom_id',
        'purchase_order_line_ids.order_id.state',
    )
    def _compute_qtys(self):
        Move = self.env['stock.move'].sudo()
        for line in self:
            # Comprado
            managed = 0.0
            for pol in line.purchase_order_line_ids.filtered(lambda l: l.order_id.state != 'cancel'):
                pol_uom = pol.product_uom_id or pol.product_id.uom_id
                tgt_uom = line.product_uom_id or pol_uom
                managed += pol_uom._compute_quantity(pol.product_qty, tgt_uom)

            # Abastecido
            supplied = 0.0
            if line.id:
                moves = Move.search([('approval_line_id', '=', line.id), ('state', '!=', 'cancel')])
                for mv in moves:
                    mv_uom = mv.product_uom or mv.product_id.uom_id
                    tgt_uom = line.product_uom_id or mv_uom
                    supplied += mv_uom._compute_quantity(mv.product_uom_qty, tgt_uom)

            pending = (line.quantity or 0.0) - managed - supplied

            line.qty_purchased = managed
            line.supplied_qty = supplied
            line.qty_pending_to_buy = pending if pending > 0 else 0.0

            _logger.debug(
                "[APL COMPUTE] apl_line=%s qty=%s purchased=%.4f supplied=%.4f pending=%.4f",
                line.id, line.quantity, managed, supplied, line.qty_pending_to_buy
            )
