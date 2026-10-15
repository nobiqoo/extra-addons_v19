# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    include_initial_balance = fields.Boolean(store=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)