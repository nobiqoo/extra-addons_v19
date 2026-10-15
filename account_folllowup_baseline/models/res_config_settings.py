# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    followup_policy = fields.Boolean(
        related='company_id.followup_policy',
        string='Follow-up Policy',
        help="Activate or deactivate the follow-up policy filter.",
        readonly=False
    )

    followup_account_ids = fields.Many2many(
        'account.account',
        related='company_id.followup_account_ids',
        string='Allowed Accounts',
        help="Select the accounts that are allowed for follow-up actions.",
        readonly=False
    )

    followup_excluded_journal_ids = fields.Many2many(
        related='company_id.followup_excluded_journal_ids',
        readonly=False,
    )