# -*- coding: utf-8 -*-

from odoo import models, fields, api


class negative_inventory(models.Model):

    _inherit = 'res.company'

    negative_inventory = fields.Boolean(
        string='Negative Inventory',
        help='Allow negative inventory.',
        default=False,
    )