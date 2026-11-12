# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    user_ids = fields.Many2many(
        'res.users', string='Users', help='Users allowed to validate operations about this warehouse.'
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
    )