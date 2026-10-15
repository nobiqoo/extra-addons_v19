# -*- coding: utf-8 -*-

from odoo import models, fields


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    x_dim_number = fields.Char(
        related='move_id.x_dim_number',
        string="DIM",
        store=True,
        readonly=False,
        copy=False,
        help="Declaración de Importación de Mercancías",
    )
