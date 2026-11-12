# -*- coding: utf-8 -*-

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_approve(self, force=False):
        result = super().button_approve(force=force)
        self.filtered(lambda o: o.state == 'purchase').order_line._assign_lot_names_from_analytic_account()
        return result
