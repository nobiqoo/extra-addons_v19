# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import html2plaintext


class StockLot(models.Model):
    _inherit = 'stock.lot'

    note_plain = fields.Text(
        string='Traceability Note',
        compute='_compute_note_plain',
        inverse='_inverse_note_plain',
        store=True,
        tracking=True,
    )
    purchase_import_ids = fields.Many2many(
        'purchase.import',
        'stock_lot_purchase_import_rel',
        'lot_id',
        'purchase_import_id',
        string='Imports',
        readonly=True,
        copy=False,
        bypass_search_access=True,
        help='Imports through which this lot/serial number was received.',
    )
    purchase_import_names = fields.Char(
        string='Import Number',
        compute='_compute_purchase_import_names',
        store=True,
        index='trigram',
        readonly=True,
    )

    @api.depends('purchase_import_ids.name')
    def _compute_purchase_import_names(self):
        for lot in self.sudo():
            lot.purchase_import_names = ', '.join(lot.purchase_import_ids.sorted('id').mapped('name')) or False

    @api.depends('note')
    def _compute_note_plain(self):
        for lot in self:
            lot.note_plain = html2plaintext(lot.note) if lot.note else False

    def _inverse_note_plain(self):
        for lot in self:
            lot.note = Markup('<p>%s</p>') % lot.note_plain if lot.note_plain else False
