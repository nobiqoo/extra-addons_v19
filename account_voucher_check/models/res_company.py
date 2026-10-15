# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from odoo import models, tools, _, api
from markupsafe import Markup
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

try:
    from num2words import num2words
except ImportError:
    _logger.warning("The num2words python library is not installed, amount-to-text features won't be fully available.")
    num2words = None


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def amount_to_text_without_cents(self, amount):
        self.ensure_one()
        # amount = int(amount)
        def _num2words(number, lang):
            try:
                return num2words(number, lang=lang).title()
            except NotImplementedError:
                return num2words(number, lang='en').title()

        if num2words is None:
            logging.getLogger(__name__).warning("The library 'num2words' is missing, cannot render textual amounts.")
            return ""

        integral, _sep, fractional = f"{amount:.{2}f}".partition('.')
        integer_value = int(integral)
        lang = tools.get_lang(self.env)
        if self.is_zero(amount - integer_value):
            return _(
                '%(integral_amount)s %(currency_unit)s',
                integral_amount=_num2words(integer_value, lang=lang.iso_code),
                currency_unit=self.currency_unit_label,
            )
        else:
            return _(
                '%(integral_amount)s %(currency_unit)s %(fractional_amount)s %(currency_subunit)s',
                integral_amount=_num2words(integer_value, lang=lang.iso_code),
                currency_unit=self.currency_unit_label,
                fractional_amount=fractional + '/100',
                currency_subunit='',
            )

    @api.model
    def remove_html_tags(self, text):
        clean_text = ''
        if isinstance(text, Markup):
            text = text.unescape()
        if text:
            clean_text = re.sub(r'<[^>]*>', '', text)
        return clean_text

class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def remove_html_tags(self, text):
        clean_text = ''
        if isinstance(text, Markup):
            text = text.unescape()
        if text:
            clean_text = re.sub(r'<[^>]*>', '', text)
        return clean_text

    def fix_date_5_hours(self, date):
        return date - relativedelta(hours=5)

    def _get_date_with_5_hours_less(self, date):
        if date:
            return date - relativedelta(hours=5)
        return date
