# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    city_id = fields.Many2one(
        'res.city',
        string="Ciudad",
        help="Ciudad relacionada con esta línea de pedido.",
    )

    @api.onchange('product_id')
    def _onchange_city_id(self):
        self.city_id = self.order_id.city_id

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move=move)
        res['city_id'] = self.city_id.id
        return res
