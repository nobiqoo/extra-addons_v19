# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError


class StockInventoryAdjustmentName(models.TransientModel):
    _inherit = 'stock.inventory.adjustment.name'

    def action_apply(self):
        if not self.env.user.has_group('stock_adjustments.group_physical_inventory_apply'):
            raise UserError(
                _("Only users with the 'Physical Inventory Apply' access rights can update the inventory."))
        return super(StockInventoryAdjustmentName, self).action_apply()
