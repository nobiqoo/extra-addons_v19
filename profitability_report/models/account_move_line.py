# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super().action_post()

        moves = self.filtered(lambda m: m.state == 'posted' and m.move_type in (
            'out_invoice', 'out_refund'))
        if moves:
            Mapping = self.env['sale.picking.invoice.mapping']
            for mv in moves:
                try:
                    Mapping.ensure_mappings_for_invoice(
                        mv, force=False, apply_to_lines=True)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Error generando mapeos picking<->factura para %s", mv.name
                    )

        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    stock_picking_id = fields.Many2one(
        'stock.picking', string='Stock Picking', copy=False, readonly=True)
