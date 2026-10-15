
from odoo import fields, models

ACCOUNT_DOMAIN = "[('account_type', 'not in', ('asset_receivable','liability_payable','asset_cash','liability_credit_card','off_balance'))]"


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    property_account_cost_sale_id = fields.Many2one(
        comodel_name='account.account',
        company_dependent=True,
        string='Cost of Sale Account',
        domain=ACCOUNT_DOMAIN,
        help='Keep this field empty to use the default value from the product category.'
    )
    property_account_cost_operation_id = fields.Many2one(
        comodel_name='account.account',
        company_dependent=True,
        string='Cost of Operation Account',
        domain=ACCOUNT_DOMAIN,
        help='Keep this field empty to use the default value from the product category.'
    )

    def _get_product_accounts(self):
        product_accounts = super(ProductTemplate, self)._get_product_accounts()
        if self.env.context.get('analytic_type'):
            analytic_type = self.env.context.get('analytic_type')
            accounts = {
                'cost_sale': self.property_account_cost_sale_id or self.categ_id.property_account_cost_sale_categ_id,
                'cost_operation': self.property_account_cost_operation_id or self.categ_id.property_account_cost_operation_categ_id
            }
            if accounts.get(analytic_type):
                product_accounts.update(expense=accounts.get(analytic_type))
        return product_accounts
