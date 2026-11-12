# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    lot_note_plain = fields.Text(
        string='Traceability Note',
        related='lot_id.note_plain',
        readonly=True,
    )
    lot_note = fields.Text(
        string='Traceability Note',
        related='lot_id.note_plain',
        readonly=False,
    )
    pending_lot_note = fields.Text(
        string='Traceability Note',
        help='Observacion capturada antes de que exista el lote. Se aplica al lote nuevo en cuanto lo crea, al validar.',
    )
    lot_purchase_import_names = fields.Char(
        string='Import Number',
        related='lot_id.purchase_import_names',
    )

    def _prepare_new_lot_vals(self):
        vals = super()._prepare_new_lot_vals()
        if self.pending_lot_note:
            vals['note'] = Markup('<p>%s</p>') % self.pending_lot_note
        return vals
