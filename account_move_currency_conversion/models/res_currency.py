# -*- coding: utf-8 -*-
from odoo import api, models


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def _get_conditioned_rate(self, partner, base_rate):
        """Apply the partner's conditioned exchange rate (TRM) adjustment, if any,
        on top of ``base_rate``.

        ``base_rate`` is expected to be an amount of company currency equivalent to
        one unit of a foreign currency (i.e. the TRM itself), so that a fixed
        adjustment can be added to it directly and a percentage adjustment can be
        applied as a share of it.
        """
        if not partner or not partner.conditioned_rate_type:
            return base_rate
        if partner.conditioned_rate_type == 'fixed':
            return base_rate + partner.conditioned_rate_value
        return base_rate * (1 + partner.conditioned_rate_value / 100.0)

    @api.model
    def _get_conditioned_conversion_rate(self, from_currency, to_currency, partner=None, company=None, date=None):
        """Return the rate to convert an amount from ``from_currency`` to
        ``to_currency`` (``to_amount = from_amount * rate``), applying the
        partner's conditioned exchange rate (TRM) adjustment, if configured, to
        whichever currency involved is not the company currency.

        The conversion always relies on Odoo's own exchange rate configuration
        (company and date aware) rather than assuming a specific currency pair,
        so it works for any combination of currencies.
        """
        if from_currency == to_currency:
            return 1.0
        company = company or self.env.company
        company_currency = company.currency_id
        base_rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company, date)
        if not partner or not partner.conditioned_rate_type:
            return base_rate
        if company_currency not in (from_currency, to_currency):
            rate_from_company = self._get_conditioned_conversion_rate(from_currency, company_currency, partner, company, date)
            rate_to_company = self._get_conditioned_conversion_rate(company_currency, to_currency, partner, company, date)
            return rate_from_company * rate_to_company
        if from_currency == company_currency:
            # base_rate is to_currency units per 1 company currency unit, i.e. the
            # inverse of the TRM of to_currency against the company currency.
            base_trm = (1.0 / base_rate) if base_rate else 0.0
            adjusted_trm = self._get_conditioned_rate(partner, base_trm)
            return (1.0 / adjusted_trm) if adjusted_trm else 0.0
        # to_currency is the company currency, so base_rate already is the TRM of
        # from_currency against the company currency.
        return self._get_conditioned_rate(partner, base_rate)

    def _convert_conditioned(self, from_amount, to_currency, partner=None, company=None, date=None, round=True):  # noqa: A002
        """Same as ``_convert``, but applying the partner's conditioned exchange
        rate (TRM) adjustment, if any, when computing the conversion rate.
        """
        self, to_currency = self or to_currency, to_currency or self
        if not from_amount:
            return 0.0
        rate = self.env['res.currency']._get_conditioned_conversion_rate(self, to_currency, partner, company, date)
        to_amount = from_amount * rate
        return to_currency.round(to_amount) if round else to_amount
