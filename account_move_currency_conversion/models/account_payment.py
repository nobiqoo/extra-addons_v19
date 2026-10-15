# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    applied_exchange_rate = fields.Float(
        string='Applied Exchange Rate (TRM)',
        digits=(16, 6),
        copy=False,
        help=(
            "Exchange rate (TRM) actually used to convert this payment's amount to the "
            "company currency when its journal entry was generated, including the "
            "partner's conditioned exchange rate adjustment, if any. Kept here for "
            "traceability and never recomputed afterwards, even if the partner's "
            "configuration or the standard rate changes later. Left empty when the "
            "payment is already in the company currency, or before the journal entry "
            "is generated."
        ),
    )

    def _prepare_move_lines_per_type(self, write_off_line_vals=None, force_balance=None):
        """Same as the original method, but recomputing the liquidity (and, to keep the
        entry balanced, the counterpart) line using the exchange rate (TRM) conditioned
        for the payment's partner, so customer receipts and vendor payments use the same
        centralized conversion logic as sale and purchase invoices.
        """
        self.ensure_one()
        result = super()._prepare_move_lines_per_type(write_off_line_vals=write_off_line_vals, force_balance=force_balance)

        company_currency = self.company_id.currency_id
        if force_balance is not None or not self.partner_id or self.currency_id == company_currency:
            return result

        liquidity_line = result['liquidity_lines'][0]
        counterpart_line = result['counterpart_lines'][0]
        write_off_balance = sum(line['balance'] for line in result['write_off_lines'])
        withholding_balance = sum(line['balance'] for line in result['withholding_lines'])

        # Since the destination currency is the company currency, this rate already is
        # the TRM (company currency units per 1 unit of the payment's currency).
        rate = self.env['res.currency']._get_conditioned_conversion_rate(
            self.currency_id, company_currency, self.partner_id, self.company_id, self.date,
        )
        liquidity_line['balance'] = company_currency.round(liquidity_line['amount_currency'] * rate)
        counterpart_line['balance'] = -liquidity_line['balance'] - write_off_balance - withholding_balance
        self.applied_exchange_rate = rate
        return result

    @api.depends(
        'move_id.amount_total_signed', 'amount', 'payment_type', 'currency_id',
        'date', 'company_id', 'company_currency_id', 'partner_id',
    )
    def _compute_amount_company_currency_signed(self):
        for payment in self:
            if payment.move_id:
                liquidity_lines = payment._seek_for_lines()[0]
                payment.amount_company_currency_signed = sum(liquidity_lines.mapped('balance'))
            else:
                payment.amount_company_currency_signed = payment.currency_id._convert_conditioned(
                    payment.amount_signed,
                    payment.company_currency_id,
                    payment.partner_id,
                    payment.company_id,
                    payment.date,
                )
