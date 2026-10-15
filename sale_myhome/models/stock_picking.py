# -*- coding: utf-8 -*-

from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    tracking_number = fields.Char(
        string='Número de Guía',
        help='Propagado automáticamente desde la Orden de Venta',
        copy=False,
    )