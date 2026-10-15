# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    voucher_advance_ids = fields.One2many(
        comodel_name="account.voucher",
        inverse_name="purchase_order_id",
        string="Advances",
    )
