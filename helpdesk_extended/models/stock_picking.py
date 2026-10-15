# -*- coding: utf-8 -*-

from odoo import fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    product_ticket_id = fields.Many2one('helpdesk.ticket',
                                        'ticket product')
