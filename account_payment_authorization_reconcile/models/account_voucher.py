# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    authorization_number = fields.Char(
        string='Authorization Number',
        copy=False,
        tracking=True,
        help=(
            "Bank authorization or approval number provided for an electronic customer "
            "receipt (bank transfer, credit/debit card, payment link, etc.). It is used by "
            "the bank reconciliation engine to automatically match this voucher with the "
            "corresponding bank statement line."
        ),
    )
    authorization_number_required = fields.Boolean(
        compute='_compute_authorization_number_required',
        help="Technical field used to make the Authorization Number mandatory on the voucher form.",
    )

    @api.depends('partner_type', 'journal_id.type')
    def _compute_authorization_number_required(self):
        for voucher in self:
            voucher.authorization_number_required = (
                voucher.partner_type == 'customer' and voucher.journal_id.type != 'cash'
            )

    def action_post(self):
        self._check_authorization_number_required()
        return super().action_post()

    def _check_authorization_number_required(self):
        invalid_vouchers = self.filtered(
            lambda voucher: voucher.authorization_number_required and not voucher.authorization_number
        )
        if invalid_vouchers:
            raise UserError(_(
                "Please set the Authorization Number before validating the following customer "
                "voucher(s): %(vouchers)s",
                vouchers=', '.join(invalid_vouchers.mapped('display_name')),
            ))
