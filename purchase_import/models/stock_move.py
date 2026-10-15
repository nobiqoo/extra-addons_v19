# -*- coding: utf-8 -*-

from odoo.tools.float_utils import float_round
from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    purchase_import_id = fields.Many2one(
        comodel_name='purchase.import',
        copy=False
    )

    x_dim_number = fields.Char(
        string="DIM",
        copy=False,
        help="Declaración de Importación de Mercancías",
    )

    def action_open_product_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.product_id.product_tmpl_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_move_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_ref': 'stock.view_stock_move_operations'},
        }

    def get_price_unit(self):
        self.ensure_one()
        return self._get_price_unit()

    def _get_price_unit(self):
        self.ensure_one()
        if self.purchase_import_id and not self.origin_returned_move_id and self.purchase_line_id and self.product_id.id == self.purchase_line_id.product_id.id:
            price_unit_prec = self.env['decimal.precision'].precision_get(
                'Product Price'
            )
            line = self.purchase_line_id
            order = line.order_id
            price_unit = line.price_unit
            if line.tax_ids:
                qty = line.product_qty or 1
                price_unit = line.tax_ids.with_context(round=False).compute_all(
                    price_unit, currency=line.order_id.currency_id, quantity=qty
                )['total_void']
                price_unit = float_round(
                    price_unit / qty, precision_digits=price_unit_prec
                )
            if line.product_uom_id.id != line.product_id.uom_id.id:
                price_unit *= line.product_uom_id.factor / line.product_id.uom_id.factor
            if order.currency_id != order.company_id.currency_id:
                price_unit = order.currency_id._convert(
                    price_unit,
                    order.company_id.currency_id,
                    order.company_id,
                    self.purchase_import_id.date_rate or fields.Date.today(),
                    round=False
                )
            return price_unit
        return super(StockMove, self)._get_price_unit()
