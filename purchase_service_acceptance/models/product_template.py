# -*- coding: utf-8 -*-

from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.depends('type')
    def _compute_purchase_method(self):
        """Native Odoo hardcodes Service products to 'purchase' (control bills on
        ordered quantities), regardless of the system default. This project wants
        Services to behave like Goods instead: billed on received quantities by
        default, so the Service Acceptance actually gates invoicing (matching the
        native flow for stockable products). Users can still override it manually
        per product."""
        default_purchase_method = self.env['product.template'].default_get(['purchase_method']).get('purchase_method', 'receive')
        for product in self:
            product.purchase_method = default_purchase_method
