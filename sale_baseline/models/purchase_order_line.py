# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.model
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, partner_id, po):
        res = super()._prepare_purchase_order_line(
            product_id, product_qty, product_uom, company_id, partner_id, po)
        if self.env.context.get('mto_by_demand'):
            res['name'] = product_id.display_name
        return res
