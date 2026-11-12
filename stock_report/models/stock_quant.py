from odoo import fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    last_movement_user_date = fields.Date(string='Último movimiento Usuario')
    last_movement_system_date = fields.Datetime(
        string='Último movimiento Sistema',
        compute='_compute_last_movement_system_date',
    )

    def _compute_last_movement_system_date(self):
        products = self.mapped('product_id')
        locations = self.mapped('location_id')
        base_domain = [
            ('product_id', 'in', products.ids),
            ('state', '=', 'done'),
        ]

        date_by_key = {}
        for location_field in ('location_id', 'location_dest_id'):
            grouped_moves = self.env['stock.move']._read_group(
                base_domain + [(location_field, 'in', locations.ids)],
                ['product_id', location_field],
                ['date:max'],
            )
            for product, location, move_date in grouped_moves:
                if not product or not location or not move_date:
                    continue
                key = (product.id, location.id)
                if key not in date_by_key or move_date > date_by_key[key]:
                    date_by_key[key] = move_date

        for quant in self:
            quant.last_movement_system_date = date_by_key.get((
                quant.product_id.id,
                quant.location_id.id,
            ))
