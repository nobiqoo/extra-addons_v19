# -*- coding: utf-8 -*-

import re

from odoo import models
from markupsafe import Markup

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def _prepare_repairs_default_value(self):
        res = super()._prepare_repairs_default_value()
        res['default_internal_notes'] = False
        res['default_service_reasons'] = self.remove_html_tags(self.description)
        return res

    def remove_html_tags(self, text):
        clean_text = ''
        if isinstance(text, Markup):
            text = text.unescape()
        if text:
            clean_text = re.sub(r'<[^>]*>', '', text)
        return clean_text

    def remove_p_tags(self, text):
        clean_text = ''
        if isinstance(text, Markup):
            clean_text = Markup(str(text).replace("<p>", '<p style="margin-bottom: 0;">'))
        else:
            clean_text = text
        return clean_text
