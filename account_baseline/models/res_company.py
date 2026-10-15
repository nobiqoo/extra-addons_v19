# -*- coding: utf-8 -*-

from odoo import _, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    fiscalyear_lock_except = fields.Boolean(
        'Lock Date Exception',
        help='Allows block dates when there are draft seats.'
    )
    manage_partner_in_invoice_lines_out = fields.Boolean(
        'Manage partner in sales invoice lines',
        help='Allows to change the partner from the sales invoice lines and '
        'these will be assigned to the account income and '
        'the partner in the header will be assigned to the '
        'account receivable.'
    )
    manage_partner_in_invoice_lines_in = fields.Boolean(
        'Manage partner in supplier invoice lines',
        help='Allows to change the partner from the supplier invoice lines and '
        'these will be assigned to the account expense and '
        'the partner in the header will be assigned to the '
        'account payable.'
    )

    close_date_validation = fields.Boolean(
        string="Remove validation in account close dates", default=False)
    account_journal_tax_with_discount_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta De IVA con Descuento del 100%',
    )
