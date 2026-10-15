# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    followup_policy = fields.Boolean('Follow-up Policy',
        help="Activate or deactivate the follow-up policy filter."
    )

    # relation/column1/column2 explícitos: sin esto, Odoo nombra la tabla
    # pivote solo a partir del par de modelos (account.account, res.company),
    # y en v19 coincide exactamente con la de account.account.company_ids
    # (también sin relation= explícito), haciendo que ambos campos compartan
    # la misma tabla y se contaminen entre sí.
    followup_account_ids = fields.Many2many(
        'account.account',
        relation='res_company_followup_account_rel',
        column1='company_id',
        column2='account_id',
        string='Allowed Accounts',
        help="Select the accounts that are allowed for follow-up actions."
    )

    followup_excluded_journal_ids = fields.Many2many(
        'account.journal',
        string='Diarios Excluidos'
    )