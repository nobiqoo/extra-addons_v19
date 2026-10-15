# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    can_edit_po = fields.Boolean(
        string="Can Edit Purchase Order",
        compute="_compute_can_edit_po",
    )

    @api.depends('state')
    def _compute_can_edit_po(self):
        editable_states = {"draft", "sent", "to approve"}
        for order in self:
            order.can_edit_po = order.state in editable_states
