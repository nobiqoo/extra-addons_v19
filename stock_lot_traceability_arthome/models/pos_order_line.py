# -*- coding: utf-8 -*-

from odoo import api, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model
    def get_existing_lots(self, company_id, config_id, product_id):
        lots = super().get_existing_lots(company_id, config_id, product_id)
        if not lots:
            return lots
        notes_by_lot = {
            lot.id: lot.note_plain
            for lot in self.env['stock.lot'].sudo().browse([lot['id'] for lot in lots])
        }
        for lot in lots:
            lot['note_plain'] = notes_by_lot.get(lot['id']) or ''
        return lots