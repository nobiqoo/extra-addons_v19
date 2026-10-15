# -*- coding: utf-8 -*-

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        purchase_orders = self.filtered(
            lambda p: p.picking_type_code == 'incoming'
        ).purchase_id
        imports = self.env['purchase.import']
        if purchase_orders:
            imports |= self.env['purchase.import'].search([
                ('purchases_ids', 'in', purchase_orders.ids)
            ])
        imports |= self.env['purchase.import'].search([
            ('pickings_ids', 'in', self.ids)
        ])
        # Snapshot moves/lines before validating: this fixes each import
        # to the pickings it currently owns, so a backorder created by
        # this validation (belonging to a later, separate import) is not
        # pulled in and does not block this import from closing.
        imports = imports.filtered(lambda r: r.state == 'confirm')
        for record in imports:
            record.action_moves()
            record.action_lines()

        # from_import=True skips purchase_import's blocking UserError,
        # letting the picking validate normally from Inventory/Purchase.
        res = super(StockPicking, self.with_context(from_import=True)).button_validate()

        if res is True:
            imports._finalize_validate()

        return res
