# -*- coding: utf-8 -*-

from odoo import fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    lot_note = fields.Text(
        string='Traceability Note',
        related='lot_id.note_plain',
        readonly=False,
    )
    lot_purchase_import_names = fields.Char(
        string='Import Number',
        related='lot_id.purchase_import_names',
    )
