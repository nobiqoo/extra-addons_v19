
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    ifrs_account_id = fields.Many2one(
        comodel_name='account.account',
        string='IFRS Account',
    )

    ifrs_account_ids = fields.One2many(
        comodel_name='account.account',
        inverse_name='ifrs_account_id',
        string='IFRS Accounts',
    )

    ifrs_is = fields.Boolean(
        string='Is IFRS?',
        default=False,
    )
