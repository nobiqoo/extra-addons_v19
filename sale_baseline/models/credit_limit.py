# -*- coding: utf-8 -*-

from odoo import models, fields


class CreditLimitHistory(models.Model):
    _name = "credit.limit.history"
    _description = "Credit Limit History"

    name = fields.Char()
    date = fields.Datetime()
    user_id = fields.Many2one('res.users', 'User who updated')
    credit = fields.Float('Credit')
    partner_id = fields.Many2one('res.partner')
