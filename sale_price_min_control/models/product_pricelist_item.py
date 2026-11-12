# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    min_price = fields.Float(
        string='Precio Mínimo',
        min_display_digits='Product Price',
        help="Precio unitario neto mínimo permitido en las órdenes de venta, "
             "expresado en la moneda de la lista y en la unidad de medida del "
             "producto. Si es cero, no se controla el precio mínimo.",
    )

    @api.constrains('min_price', 'fixed_price', 'compute_price')
    def _check_min_price(self):
        """Valida que el precio mínimo no supere el precio fijo de la regla."""
        precision = self.env['decimal.precision'].precision_get('Product Price')
        for item in self:
            if item.min_price < 0:
                raise ValidationError(_("El precio mínimo no puede ser negativo."))
            if item.compute_price == 'fixed' and float_compare(
                    item.min_price, item.fixed_price, precision_digits=precision) > 0:
                raise ValidationError(_(
                    "El precio mínimo (%(min)s) no puede ser mayor que el precio "
                    "fijo de la regla (%(price)s).",
                    min=item.min_price, price=item.fixed_price,
                ))
