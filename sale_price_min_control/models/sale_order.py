# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError

PRICE_EXCEPTION_RESET_FIELDS = {'price_unit', 'discount', 'product_id', 'product_uom_qty', 'product_uom_id'}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    price_exception_approved = fields.Boolean(
        string='Excepción de Precio Mínimo Aprobada',
        copy=False,
    )
    has_price_exception = fields.Boolean(
        string='Tiene Precio Bajo el Mínimo',
        compute='_compute_has_price_exception',
    )

    @api.depends('order_line.price_unit', 'order_line.discount', 'order_line.product_id',
                 'order_line.product_uom_qty', 'order_line.product_uom_id',
                 'pricelist_id', 'date_order')
    def _compute_has_price_exception(self):
        for order in self:
            order.has_price_exception = bool(order._get_price_exception_lines())

    def _get_price_exception_lines(self):
        """Retorna las líneas cuyo precio neto es inferior al mínimo de su regla de lista."""
        self.ensure_one()
        return self.order_line.filtered(lambda line: line._is_below_min_price())

    def _confirmation_error_message(self):
        error_msg = super()._confirmation_error_message()
        if error_msg:
            return error_msg
        self.ensure_one()
        if not self.price_exception_approved and self._get_price_exception_lines():
            return _(
                "La cotización contiene productos con precios inferiores al "
                "mínimo permitido de la lista de precios. Contacte al "
                "Responsable Comercial para autorizar la excepción."
            )
        return False

    def action_approve_price_exception(self):
        if not self.env.user.has_group('sale_price_min_control.group_price_exception_approver'):
            raise AccessError(_(
                "No tiene permiso para aprobar excepciones de precio mínimo."
            ))
        for order in self:
            order.price_exception_approved = True
            order.message_post(
                body=_("Excepción de precio mínimo aprobada por %s.", self.env.user.name)
            )

    def write(self, vals):
        if 'pricelist_id' in vals:
            vals = dict(vals, price_exception_approved=False)
        return super().write(vals)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_min_allowed_price(self):
        """Retorna el precio mínimo de la regla de lista aplicada, en la moneda y UdM de la línea."""
        self.ensure_one()
        rule = self.pricelist_item_id
        if self.display_type or not self.product_id or not rule.min_price:
            return 0.0
        min_price = rule.min_price
        if self.product_uom_id and self.product_id.uom_id != self.product_uom_id:
            min_price = self.product_id.uom_id._compute_price(min_price, self.product_uom_id)
        if rule.currency_id and self.currency_id and rule.currency_id != self.currency_id:
            min_price = rule.currency_id._convert(
                min_price, self.currency_id, self.company_id, self._get_order_date())
        return min_price

    def _is_below_min_price(self):
        """Indica si el precio neto (con descuento) de la línea es inferior al mínimo permitido."""
        self.ensure_one()
        min_price = self._get_min_allowed_price()
        if not min_price:
            return False
        net_price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        currency = self.currency_id or self.company_id.currency_id
        return currency.compare_amounts(net_price, min_price) < 0

    def write(self, vals):
        res = super().write(vals)
        if PRICE_EXCEPTION_RESET_FIELDS & vals.keys():
            orders = self.order_id.filtered('price_exception_approved')
            if orders:
                orders.write({'price_exception_approved': False})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        orders = lines.order_id.filtered('price_exception_approved')
        if orders:
            orders.write({'price_exception_approved': False})
        return lines
