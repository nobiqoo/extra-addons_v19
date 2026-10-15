from odoo import api, models
from .mixin import ProductIdOnchangeMixin


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    mixin = ProductIdOnchangeMixin()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.env.company.activate_filter_sale:
            return self.mixin._onchange_product_id_common(self.order_id)
