# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    journal_id = fields.Many2one(
        related='company_id.journal_id',
        readonly=False
    )
    advance_req_in_immediate_pay = fields.Boolean(
        related='company_id.advance_req_in_immediate_pay',
        readonly=False
    )
    active_payment_advance = fields.Boolean(
        related='company_id.active_payment_advance',
        readonly=False
    )

    voucher_account_id = fields.Many2one(
        related='company_id.voucher_account_id',
        readonly=False
    )
    advance_account_loan_id = fields.Many2one(
        related='company_id.advance_account_loan_id',
        string='Cuenta De Préstamo Empleados',
        readonly=False
    )
    voucher_in_payment_state = fields.Boolean(
        related='company_id.voucher_in_payment_state',
        string='Voucher in payment state',
        readonly=False
    )
    use_transient_account = fields.Boolean(
        related='company_id.use_transient_account',
        string='Usar cuenta transitoria en pagos',
        readonly=False
    )
