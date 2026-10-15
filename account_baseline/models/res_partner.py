# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    account_type = fields.Selection(
        selection=[
            ('saving', 'Saving'),
            ('current', 'Current'),
        ],
        string='Account type',
        default='saving'
    )

    use_partner_credit_limit = fields.Boolean(
        string='Partner Limit',
        groups='account.group_account_invoice,account.group_account_readonly',
        compute=False,
        inverse=False,
        store=True,
        help='Set a value greater than 0.0 to activate a credit limit check'
    )
