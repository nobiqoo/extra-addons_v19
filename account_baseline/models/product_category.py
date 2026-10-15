# -*- coding: utf-8 -*-

from odoo import models, fields

ACCOUNT_DOMAIN = "[('account_type', 'not in', ('asset_receivable','liability_payable','asset_cash','liability_credit_card','off_balance'))]"


class ProductCategory(models.Model):
    _inherit = 'product.category'

    property_account_refund_categ_id = fields.Many2one(
        'account.account',
        company_dependent=True,
        string='Refund Account',
        domain=ACCOUNT_DOMAIN,
        help='This account will be used when validating a customer refund.')
