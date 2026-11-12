from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    manual_lot_ids = fields.Many2many(
        'stock.lot', 'account_move_line_manual_lot_rel',
        string='Números de Serie Manual')
    lot_ids = fields.Many2many(
        'stock.lot', string='Números de Serie',
        compute='_compute_lot_ids', inverse='_inverse_lot_ids')
    available_lot_ids = fields.Many2many(
        'stock.lot', 'account_move_line_available_lot_rel',
        string='Números de Serie Disponibles',
        compute='_compute_available_lot_ids', readonly=True)

    @api.depends('manual_lot_ids', 'move_id.move_type', 'available_lot_ids')
    def _compute_lot_ids(self):
        for line in self:
            if line.move_id.move_type in ('out_refund', 'in_refund'):
                if not line.manual_lot_ids and line.available_lot_ids:
                    line.manual_lot_ids = line.available_lot_ids
                line.lot_ids = line.manual_lot_ids
            else:
                line.lot_ids = line.available_lot_ids

    @api.depends(
        'product_id',
        'move_id.move_type',
        'sale_line_ids.move_ids.state',
        'sale_line_ids.move_ids.product_id',
        'sale_line_ids.move_ids.lot_ids',
        'sale_line_ids.move_ids.move_line_ids.lot_id',
        'sale_line_ids.move_ids.move_line_ids.quantity',
        'sale_line_ids.move_ids.location_id.usage',
        'sale_line_ids.move_ids.location_dest_id.usage',
        'sale_line_ids.move_ids.picking_id.move_ids.state',
        'sale_line_ids.move_ids.picking_id.move_ids.product_id',
        'sale_line_ids.move_ids.picking_id.move_ids.location_id.usage',
        'sale_line_ids.move_ids.picking_id.move_ids.location_dest_id.usage',
        'sale_line_ids.move_ids.picking_id.move_ids.move_line_ids.lot_id',
        'sale_line_ids.move_ids.picking_id.move_ids.move_line_ids.quantity',
    )
    def _compute_available_lot_ids(self):
        for line in self:
            line.available_lot_ids = line._get_available_lots()

    @api.onchange('product_id')
    def _onchange_product_id_set_manual_lots(self):
        if self.move_id.move_type in ('out_refund', 'in_refund') and not self.manual_lot_ids:
            lots = self.available_lot_ids or self._get_available_lots()
            self.manual_lot_ids = lots
            self.lot_ids = lots

    def _inverse_lot_ids(self):
        for line in self:
            if line.move_id.move_type in ('out_refund', 'in_refund'):
                line.manual_lot_ids = line.lot_ids

    def _get_related_picking_lines(self):
        self.ensure_one()
        moves = self.sale_line_ids.move_ids
        if self.move_id.move_type == 'out_invoice':
            # Include operations added to a related delivery even when they do
            # not carry sale_line_id. Product filtering is applied below.
            moves |= moves.picking_id.move_ids
            moves = moves.filtered(
                lambda move: move.location_dest_id.usage == 'customer'
                and move.location_id.usage != 'customer'
            )
        return moves

    def _get_available_lots(self):
        self.ensure_one()
        if not self.product_id:
            return self.env['stock.lot']
        move_ids = self._get_related_picking_lines().filtered(
            lambda move: move.product_id == self.product_id and move.state == 'done'
        )
        if self.move_id.move_type != 'out_invoice':
            return move_ids.mapped('lot_ids') or move_ids.mapped('move_line_ids.lot_id')
        operations = move_ids.move_line_ids.filtered(
            lambda operation: operation.quantity > 0
            and operation.product_id == self.product_id
        )
        return operations.lot_id.sorted(lambda lot: (lot.name or '', lot.id))
