# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import Command, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves._link_lots_to_purchase_import()
        return moves

    def _link_lots_to_purchase_import(self):
        """Registra en los lotes recibidos la importación de su movimiento."""
        lots_by_import = defaultdict(lambda: self.env['stock.lot'])
        for move in self.filtered('purchase_import_id'):
            lots_by_import[move.purchase_import_id.id] |= move.move_line_ids.lot_id
        for import_id, lots in lots_by_import.items():
            if lots:
                lots.write({'purchase_import_ids': [Command.link(import_id)]})
