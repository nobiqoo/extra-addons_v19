# -*- coding: utf-8 -*-

from odoo import models, fields, api

ACCOUNT_DOMAIN = "[('account_type', 'not in', ('asset_receivable','liability_payable','asset_cash','liability_credit_card','off_balance'))]"


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    property_account_refund_id = fields.Many2one(
        'account.account',
        company_dependent=True,
        string='Refund Account',
        domain=ACCOUNT_DOMAIN,
        help='Keep this field empty to use the default value from the product category.')

    def _get_product_accounts(self):
        accounts = super(ProductTemplate, self)._get_product_accounts()
        accounts.update(
            {'refund': self.property_account_refund_id or self.categ_id.property_account_refund_categ_id})
        if self.env.context.get('default_expense'):
            accounts.update(
                {'expense': self.env.context.get('default_expense')}
            )
        return accounts
