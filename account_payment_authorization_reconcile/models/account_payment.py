# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    authorization_number = fields.Char(
        string='Authorization Number',
        copy=False,
        tracking=True,
        help=(
            "Bank authorization or approval number provided for an electronic customer "
            "payment (bank transfer, credit/debit card, payment link, etc.). It is used by "
            "the bank reconciliation engine to automatically match this payment with the "
            "corresponding bank statement line."
        ),
    )
    authorization_number_required = fields.Boolean(
        compute='_compute_authorization_number_required',
        help="Technical field used to make the Authorization Number mandatory on the payment form.",
    )

    @api.depends('payment_type', 'journal_id.type')
    def _compute_authorization_number_required(self):
        for payment in self:
            payment.authorization_number_required = (
                payment.payment_type == 'inbound' and payment.journal_id.type != 'cash'
            )

    def action_post(self):
        self._check_authorization_number_required()
        return super().action_post()

    def _check_authorization_number_required(self):
        invalid_payments = self.filtered(
            lambda payment: payment.authorization_number_required and not payment.authorization_number
        )
        if invalid_payments:
            raise UserError(_(
                "Please set the Authorization Number before validating the following customer "
                "payment(s): %(payments)s",
                payments=', '.join(invalid_payments.mapped('display_name')),
            ))
