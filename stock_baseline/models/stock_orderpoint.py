from odoo import models, api
from odoo.tools import float_compare


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    @api.depends('qty_multiple', 'qty_forecast', 'product_min_qty', 'product_max_qty', 'visibility_days')
    def _compute_qty_to_order_computed(self):
        def to_compute(orderpoint):
            rounding = orderpoint.product_uom.rounding
            # The check is on purpose. We only want to consider the visibility days if the forecast is negative and
            # there is a already something to ressuply base on lead times.
            return (
                orderpoint.product_id
                and orderpoint.location_id
                and float_compare(orderpoint.qty_forecast, orderpoint.product_min_qty, precision_rounding=rounding) < 0
            )

        orderpoints = self.filtered(to_compute)
        qty_in_progress_by_orderpoint = orderpoints._quantity_in_progress()
        for orderpoint in orderpoints:
            orderpoint.qty_to_order_computed = orderpoint._get_qty_to_order(qty_in_progress_by_orderpoint=qty_in_progress_by_orderpoint)
        (self - orderpoints).qty_to_order_computed = False
