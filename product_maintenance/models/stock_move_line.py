# -*- coding: utf-8 -*-

from odoo import models, fields
from datetime import date
from odoo.exceptions import ValidationError


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    product_maintenance_id = fields.Many2one(
        comodel_name='product.maintenance',
        string='Producto de Mantenimiento'
    )
