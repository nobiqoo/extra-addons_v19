# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class StockQuant(models.Model):
    _inherit = "stock.quant"

    has_group_inventory_adjustment = fields.Boolean(
        string="Inventory Adjustment",
        compute="_compute_has_group_inventory_adjustment",
    )

    def _compute_has_group_inventory_adjustment(self):
        """
        Compute if the user has the group 'Inventory Adjustment' for
        stock.quant model.
        """
        for record in self:
            record.has_group_inventory_adjustment = self.env.user.has_group(
                'stock_adjustments.group_inventory_adjustments')

    def _set_inventory_quantity(self):
        """
        !OVERWRITE THIS METHOD TO NOT AUTOSET THE QUANT INVENTORY QUANTITY

        Inverse method to create stock move when `inventory_quantity` is set
        (`inventory_quantity` is only accessible in inventory mode).
        """
        if not self._is_inventory_mode():
            return
        quant_to_inventory = self.env['stock.quant']
        for quant in self:
            if quant.quantity == quant.inventory_quantity_auto_apply:
                continue
            quant.inventory_quantity = quant.inventory_quantity_auto_apply
            quant_to_inventory |= quant
        if not self.env.user.has_groups('stock_adjustments.group_physical_inventory_apply'):
            return
        quant_to_inventory.with_context(
            {'set_inventory_quantity_auto_apply': True}).action_apply_inventory()
