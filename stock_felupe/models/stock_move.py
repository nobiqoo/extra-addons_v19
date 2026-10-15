from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    cost_sharing_float = fields.Float(
        string='Reparto de Costos',
        compute='_compute_cost_sharing',
        store=True,
    )
    cost_prom = fields.Float(
        string='Costos Promedio',
        related='product_id.standard_price',
    )

    @api.depends(
        'cost_share',
        'product_uom_qty',
        'production_id.state',
        'production_id.move_raw_ids.product_id.standard_price',
        'production_id.move_raw_ids.product_uom_qty',
    )
    def _compute_cost_sharing(self):
        for move in self:
            production = move.production_id
            if not production:
                move.cost_sharing_float = 0.0
                continue

            if production.state == 'done' and move.cost_sharing_float:
                continue

            total_cost = sum(
                raw_move.product_id.standard_price * raw_move.product_uom_qty
                for raw_move in production.move_raw_ids
            )
            shared_cost = total_cost * (move.cost_share / 100.0)
            move.cost_sharing_float = (
                shared_cost / move.product_uom_qty
                if move.product_uom_qty
                else 0.0
            )
