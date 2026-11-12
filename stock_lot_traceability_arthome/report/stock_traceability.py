# -*- coding: utf-8 -*-

from odoo import api, models


class StockTraceabilityReport(models.TransientModel):
    _inherit = 'stock.traceability.report'

    def _make_dict_move(self, level, parent_id, move_line, unfoldable=False):
        data = super()._make_dict_move(level, parent_id, move_line, unfoldable=unfoldable)
        for line in data:
            line['lot_note_plain'] = move_line.lot_id.note_plain or ''
        return data

    @api.model
    def _final_vals_to_lines(self, final_vals, level):
        lines = super()._final_vals_to_lines(final_vals, level)
        for line, data in zip(lines, final_vals):
            line['columns'].append(data.get('lot_note_plain', ''))
        return lines
