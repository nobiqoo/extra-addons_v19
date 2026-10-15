# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountVoucherWizard(models.TransientModel):
    _inherit = 'account.voucher.wizard'

    authorization_number = fields.Char(
        string='Authorization Number',
        help=(
            "Bank authorization or approval number provided for an electronic customer "
            "payment (bank transfer, credit/debit card, payment link, etc.). It is used by "
            "the bank reconciliation engine to automatically match the resulting voucher "
            "with the corresponding bank statement line."
        ),
    )
    authorization_number_required = fields.Boolean(
        compute='_compute_authorization_number_required',
        help="Technical field used to make the Authorization Number mandatory on the wizard.",
    )

    @api.depends('journal_id')
    def _compute_authorization_number_required(self):
        for wizard in self:
            active_model = wizard.env.context.get('active_model')
            active_ids = wizard.env.context.get('active_ids') or []
            is_customer_invoice = bool(
                active_model
                and wizard.env[active_model].browse(active_ids).filtered(
                    lambda active: active.move_type == 'out_invoice'
                )
            )
            wizard.authorization_number_required = is_customer_invoice and wizard.journal_id.type != 'cash'

    def button_create_voucher(self):
        if self.authorization_number_required and not self.authorization_number:
            raise UserError(_("Please set the Authorization Number before registering this payment."))
        # `authorization_number` isn't part of the `values` dict built by the base method, so it
        # is threaded through as a create default instead of duplicating its voucher-creation loop.
        return super(AccountVoucherWizard, self.with_context(
            default_authorization_number=self.authorization_number
        )).button_create_voucher()
