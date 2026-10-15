# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import ValidationError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.constrains('location_id', 'quantity')
    def _check_negative_inventory(self):
        for record in self:
            location = record.location_id
            quantity = record.quantity
            product = record.product_id
            subcontract_type = False
            if location and location.usage == 'internal' and quantity < 0:
                for bom in product.bom_ids:
                    if bom.type == 'subcontract':
                        subcontract_type = True
                        break
                if not self.env.company.negative_inventory and not subcontract_type:
                    raise ValidationError(
                        _('No negative moves allowed. Location: %s, Product: %s') % (
                            location.complete_name, product.display_name
                        )
                    )
