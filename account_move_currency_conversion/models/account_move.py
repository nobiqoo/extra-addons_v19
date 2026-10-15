# -*- coding: utf-8 -*-
from odoo import api, fields, models

CONVERTIBLE_MOVE_TYPES = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')


class AccountMove(models.Model):
    _inherit = 'account.move'

    line_amounts_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Line Amounts Currency',
        copy=False,
        help=(
            "Technical field remembering the currency the invoice line amounts are "
            "currently expressed in, so that the next time the invoice currency is "
            "changed the lines can be converted from the right rate."
        ),
    )

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids_track_currency(self):
        if self.move_type in CONVERTIBLE_MOVE_TYPES:
            self.line_amounts_currency_id = self.currency_id

    @api.onchange('currency_id')
    def _onchange_currency_id_convert_lines(self):
        if self.move_type not in CONVERTIBLE_MOVE_TYPES or self.state != 'draft':
            return

        old_currency = self.line_amounts_currency_id
        new_currency = self.currency_id
        self.line_amounts_currency_id = new_currency

        if not old_currency or not new_currency or old_currency == new_currency:
            return

        product_lines = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        if not product_lines:
            return

        company = self.company_id or self.env.company
        date = self.invoice_date or fields.Date.context_today(self)
        for line in product_lines:
            line.price_unit = old_currency._convert_conditioned(
                line.price_unit, new_currency, self.partner_id, company, date,
            )

        return {
            'warning': {
                'title': self.env._("Currency conversion applied"),
                'message': self._get_currency_conversion_message(old_currency, new_currency, company, date),
            },
        }

    def _get_currency_conversion_message(self, old_currency, new_currency, company, date):
        """Build a message explaining exactly how the exchange rate (TRM) used to
        convert the invoice lines from ``old_currency`` to ``new_currency`` was
        obtained, including the partner's conditioned rate adjustment when one is
        configured, or a clear note when it is not, so the user can see where the
        rate comes from.
        """
        Currency = self.env['res.currency']
        company_currency = company.currency_id
        partner = self.partner_id

        if company_currency == old_currency and new_currency != company_currency:
            foreign_currency = new_currency
        elif company_currency == new_currency and old_currency != company_currency:
            foreign_currency = old_currency
        else:
            foreign_currency = False

        if not foreign_currency:
            # Neither currency is the company currency: there is no single TRM to
            # break down, so fall back to a plain conversion rate message.
            rate = Currency._get_conditioned_conversion_rate(old_currency, new_currency, partner, company, date)
            return self.env._(
                "The line amounts were converted from %(old_currency)s to %(new_currency)s "
                "using an exchange rate of %(rate)s.",
                old_currency=old_currency.name,
                new_currency=new_currency.name,
                rate=rate,
            )

        base_trm = Currency._get_conversion_rate(foreign_currency, company_currency, company, date)
        has_conditioned_rate = partner and partner.conditioned_rate_type and partner.conditioned_rate_value

        if not has_conditioned_rate:
            return self.env._(
                "The line amounts were converted from %(old_currency)s to %(new_currency)s "
                "using the standard exchange rate (TRM) of %(base_trm)s %(company_currency)s "
                "per %(foreign_currency)s (%(partner)s has no conditioned exchange rate "
                "configured, or its adjustment value is zero).",
                old_currency=old_currency.name,
                new_currency=new_currency.name,
                base_trm=round(base_trm, 6),
                company_currency=company_currency.name,
                foreign_currency=foreign_currency.name,
                partner=partner.display_name if partner else self.env._("this document's contact"),
            )

        adjusted_trm = Currency._get_conditioned_rate(partner, base_trm)
        if partner.conditioned_rate_type == 'fixed':
            adjustment_description = self.env._(
                "standard rate %(base_trm)s + the fixed conditioned adjustment of %(value)s "
                "configured on %(partner)s",
                base_trm=round(base_trm, 6),
                value=partner.conditioned_rate_value,
                partner=partner.display_name,
            )
        else:
            adjustment_description = self.env._(
                "standard rate %(base_trm)s + a %(value)s%% conditioned adjustment "
                "configured on %(partner)s",
                base_trm=round(base_trm, 6),
                value=partner.conditioned_rate_value,
                partner=partner.display_name,
            )
        return self.env._(
            "The line amounts were converted from %(old_currency)s to %(new_currency)s "
            "using an exchange rate (TRM) of %(adjusted_trm)s %(company_currency)s per "
            "%(foreign_currency)s (%(adjustment_description)s).",
            old_currency=old_currency.name,
            new_currency=new_currency.name,
            adjusted_trm=round(adjusted_trm, 6),
            company_currency=company_currency.name,
            foreign_currency=foreign_currency.name,
            adjustment_description=adjustment_description,
        )
