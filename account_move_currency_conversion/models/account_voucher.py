# -*- coding: utf-8 -*-
from odoo import api, models


class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    @api.depends('currency_id', 'date', 'partner_id')
    def _compute_exchange_rate(self):
        """Same as the original computation, but applying the partner's conditioned
        exchange rate (TRM) adjustment, if any, so customer receipts and vendor
        payments recorded as vouchers use the same centralized conversion logic as
        sale/purchase invoices and account.payment records.

        This rate is used everywhere in the voucher (reconciliation line suggestions
        and the generated journal entry), so overriding it here is enough to cover
        the whole voucher flow.
        """
        for voucher in self:
            voucher.exchange_rate = voucher.currency_id._convert_conditioned(
                1, voucher.company_id.currency_id, voucher.partner_id, voucher.company_id, voucher.date,
            )

    def _action_reconcile(self):
        """Force the reconciliation to use the same exchange rate (TRM) that was used
        to book this voucher's own journal entry.

        Without this, when reconciling a foreign-currency voucher against a line
        expressed in the company currency (e.g. a COP vendor bill paid through a USD
        voucher), Odoo's reconciliation engine independently recomputes the rate to
        apply using the *standard* rate for the invoice's date, ignoring the rate
        actually used to book the voucher. Since that recomputed rate hardly ever
        matches the (possibly conditioned) rate stored in ``exchange_rate``, most of
        the payment ends up wrongly booked as an exchange gain/loss instead of
        settling the invoice, leaving it still open for a large amount.

        Forcing the rate here keeps only the genuine rounding-level difference (a few
        cents) as an exchange gain/loss, while the invoice is fully settled, matching
        how the voucher was actually booked.
        """
        if self.currency_id != self.company_currency_id and self.exchange_rate:
            return super(AccountVoucher, self.with_context(
                forced_rate_from_register_payment=1.0 / self.exchange_rate,
            ))._action_reconcile()
        return super()._action_reconcile()
