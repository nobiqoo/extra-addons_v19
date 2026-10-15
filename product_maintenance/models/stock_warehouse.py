# -*- coding: utf-8 -*-

from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    enabled_for_repair = fields.Boolean(
        string='Enabled for Repairs',
        default=True,
        help='If unchecked, this warehouse will not appear as an Operation '
             'Type option on repair orders, nor be used as the default '
             'repair warehouse.'
    )
