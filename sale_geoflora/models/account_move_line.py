# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models

# Sufijo WebFlor de la etiqueta de la cuenta por cobrar, ej. "(N°124645 WF)"
WEBFLOR_LABEL_RE = re.compile(r'\s*\(N°[^()]*WF\)$')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    webflor_product_code = fields.Char(
        string='WebFlor Product ID',
        compute='_compute_webflor_line_info',
        store=True,
        readonly=False,
        copy=True,
    )
    webflor_referente = fields.Char(
        string='Referente',
        compute='_compute_webflor_line_info',
        store=True,
        readonly=False,
        copy=True,
    )

    @api.depends('sale_line_ids.webflor_product_code', 'sale_line_ids.webflor_referente')
    def _compute_webflor_line_info(self):
        """Hereda los datos WebFlor de la línea de venta mientras la factura está en borrador."""
        for line in self:
            if line.move_id.state != 'draft':
                continue
            for fname in ('webflor_product_code', 'webflor_referente'):
                values = [value for value in dict.fromkeys(line.sale_line_ids.mapped(fname)) if value]
                line[fname] = ', '.join(values) if line.sale_line_ids else line[fname]

    @api.depends('move_id.webflor_invoice_number')
    def _compute_name(self):
        """Agrega el N° Invoice WebFlor a la etiqueta de la cuenta por cobrar de las facturas de venta."""
        super()._compute_name()
        for line in self:
            move = line.move_id
            if (
                line.display_type != 'payment_term'
                or move.inalterable_hash
                or not move.is_sale_document(include_receipts=True)
            ):
                continue
            base = WEBFLOR_LABEL_RE.sub('', line.name or '')
            label = move._get_webflor_receivable_label()
            name = ' '.join(part for part in (base, label) if part)
            if name != (line.name or ''):
                line.name = name or False

    def _format_aml_name(self, line_name, move_ref, move_name=None):
        """Evita repetir "referencia - número" cuando la etiqueta trae el sufijo WebFlor."""
        if line_name and move_name and WEBFLOR_LABEL_RE.search(line_name):
            for prefix in (f'{move_ref} - {move_name}', move_name):
                if line_name.startswith(prefix):
                    line_name = line_name[len(prefix):].strip()
                    break
        return super()._format_aml_name(line_name, move_ref, move_name=move_name)
