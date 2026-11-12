from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        done_moves = res if res and hasattr(res, 'product_id') else self
        done_moves._clear_manual_last_movement_dates()
        return res

    def _clear_manual_last_movement_dates(self):
        done_moves = self.filtered(lambda move: move.state == 'done')
        products = done_moves.mapped('product_id')
        locations = done_moves.mapped('location_id') | done_moves.mapped('location_dest_id')
        if not products or not locations:
            return

        quants = self.env['stock.quant'].search([
            ('product_id', 'in', products.ids),
            ('location_id', 'in', locations.ids),
            ('last_movement_user_date', '!=', False),
        ])
        quants.write({'last_movement_user_date': False})
