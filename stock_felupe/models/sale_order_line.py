from odoo import _, api, models
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('price_unit', 'purchase_price', 'product_id', 'product_uom_qty')
    def _check_minimum_margin(self):
        for line in self:
            product = line.product_id
            if (
                not product
                or not line.price_unit
                or not line.purchase_price
                or product.margin_percentage <= 0
                or line.order_id.sale_margin
            ):
                continue

            if line.margin_percent < product.margin_percentage:
                raise ValidationError(_(
                    "El precio de venta del producto '%(product)s' "
                    "(%(price).2f) esta por debajo del margen minimo "
                    "permitido (%(minimum).2f%%).\nMargen: %(margin).2f%%",
                    product=product.display_name,
                    price=line.price_unit,
                    minimum=product.margin_percentage * 100,
                    margin=line.margin_percent * 100,
                ))

    @api.depends('price_subtotal', 'product_uom_qty', 'purchase_price')
    def _compute_margin(self):
        """Compute the business markup over cost used by Felupe.

        The standard ``sale_margin`` module computes margin percentage over
        sales.  Felupe historically compares the profit against total cost,
        so this override intentionally keeps that business definition.
        """
        for line in self:
            if line.qty_delivered and not line.product_uom_qty:
                quantity = line.qty_delivered
                subtotal = line.price_unit * quantity
            else:
                quantity = line.product_uom_qty
                subtotal = line.price_subtotal

            total_cost = line.purchase_price * quantity
            line.margin = subtotal - total_cost
            line.margin_percent = total_cost and line.margin / total_cost or 0.0
