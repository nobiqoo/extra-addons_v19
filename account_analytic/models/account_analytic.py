
from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    account_type = fields.Selection(
        selection=[
            ('income', 'Income'),
            ('expense', 'Expense'),
            ('cost_sale', 'Cost of Sale'),
            ('cost_operation', 'Cost of Operation'),
        ],
        string='Type',
    )
