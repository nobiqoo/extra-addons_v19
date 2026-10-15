# -*- coding: utf-8 -*-

from odoo import _, fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    account_advance_id = fields.Many2one(
        'account.account',
        'Account advance')
