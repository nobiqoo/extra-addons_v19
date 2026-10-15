# -*- coding: utf-8 -*-

from odoo import api, fields, models


class BankPaymentLine(models.Model):
    _inherit = "bank.payment.line"

    @api.depends("payment_line_ids", "payment_line_ids.amount_currency")
    def _compute_amount(self):
        for bline in self:
            amount_currency = sum(bline.mapped(
                "payment_line_ids.amount_currency"))
            if bline.company_id.currency_id == bline.currency_id:
                amount_company_currency = bline.currency_id._convert(
                    amount_currency,
                    bline.company_currency_id,
                    bline.company_id,
                    bline.date or fields.Date.today(),
                )
            else:
                amount_company_currency = bline.company_currency_id.round(
                    amount_currency*bline.order_id.current_exchange_rate
                )
            bline.amount_currency = amount_currency
            bline.amount_company_currency = amount_company_currency
