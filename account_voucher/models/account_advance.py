# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountAdvance(models.Model):
    _name = 'account.advance'
    _description = 'Accounting Advance'

    name = fields.Char('Description')

    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('revision', 'Revisión'),
            ('validated', 'Validado')
        ],
        default='draft'
    )

    partner_id = fields.Many2one('res.partner', 'Client')

    order_id = fields.Many2one('sale.order', 'Order')

    currency_id = fields.Many2one('res.currency')

    account_advance_id = fields.Many2one('account.move')
