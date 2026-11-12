# -*- coding: utf-8 -*-

from odoo import fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    # Odoo 19 no trae `active` nativo en stock.lot; se agrega para habilitar
    active = fields.Boolean(string='Active', default=True, tracking=True)
