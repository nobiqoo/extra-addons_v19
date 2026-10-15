# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

try:
    from odoo.addons.l10n_co_bloodo.models.ir_sentences import escape_xml
except ImportError:
    # Si el módulo no está disponible, crear una función dummy
    def escape_xml(data):
        from xml.sax.saxutils import escape
        if isinstance(data, str):
            return escape(data)
        elif isinstance(data, list):
            return [escape_xml(d) for d in data]
        elif isinstance(data, dict):
            return {k: escape_xml(v) for k, v in data.items()}
        else:
            return data


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _linienwerte_erhalten(self, trm=1):
        invoice_lines = super(AccountMove, self)._linienwerte_erhalten(trm)
        for count, line_id in enumerate(invoice_lines.keys(), 1):
            invoice_line = self.invoice_line_ids.filtered(
                lambda ln: ln.display_type == 'product'
            )[count - 1]
            invoice_lines[count]['Note'] = escape_xml(
                invoice_line.description or invoice_line.name
            )

        return invoice_lines

    def _linienwerte_ds_erhalten(self, trm=1):
        invoice_lines = super(AccountMove, self)._linienwerte_ds_erhalten(trm)
        for count, line_id in enumerate(invoice_lines.keys(), 1):
            invoice_line = self.invoice_line_ids.filtered(
                lambda ln: ln.display_type == 'product'
            )[count - 1]
            invoice_lines[count]['Note'] = escape_xml(
                invoice_line.description or invoice_line.name
            )

        return invoice_lines