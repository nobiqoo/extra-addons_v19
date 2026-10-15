# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fiscalyear_lock_except = fields.Boolean(
        related='company_id.fiscalyear_lock_except',
        readonly=False
    )
    manage_partner_in_invoice_lines_out = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_out',
        readonly=False
    )
    manage_partner_in_invoice_lines_in = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_in',
        readonly=False
    )
    account_journal_tax_with_discount_id = fields.Many2one(
        related='company_id.account_journal_tax_with_discount_id',
        string='Cuenta De IVA con Descuento del 100%',
        readonly=False
    )
