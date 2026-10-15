# -*- coding: utf-8 -*-

from datetime import date

from odoo import models, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _compute_name(self):
        """Default the line description to the product name without its
        internal reference code.

        Odoo core changed this method between 17.0 and 19.0: it now always
        prepends ``product.display_name`` (which includes the product's
        internal reference, e.g. "[COL-0117] Flete Aereo") to the line
        description. Anker's 17.0 setup never showed that code because the
        description came only from ``product.description_sale``/
        ``description_purchase``, which none of their products have
        configured, so lines were simply left blank. Replicating that
        literally in 19.0 would leave every new line without a description,
        which is worse than the code prefix. Use ``product.name`` (the
        product name without the code) instead, so the description is
        always populated and never carries the "[code] " prefix.

        Once a value is set, it is left untouched unless the product on an
        already-saved line is changed. Core's own condition
        (``line._origin.name == get_name(line._origin)``) only protects a
        manual edit once the line has been saved: for a brand new,
        not-yet-saved line ``line._origin`` is always empty, so that
        comparison is always true and any later recompute trigger (e.g. the
        invoice's ``ref``/``payment_reference`` changing, which this method
        also depends on) would silently wipe out whatever the user just
        typed and replace it with the product default. Guarding the
        "product changed" branch behind ``line._origin`` avoids that: for a
        new line the description is set once (when still blank) and never
        recomputed again, so anything the user types is what ends up on the
        printed invoice.
        """
        def get_name(line):
            values = []
            if line.move_id.partner_id.lang:
                product = line.product_id.with_context(lang=line.move_id.partner_id.lang)
            elif line.partner_id.lang:
                product = line.product_id.with_context(lang=line.partner_id.lang)
            else:
                product = line.product_id
            if not product:
                return False

            if line.journal_id.type == 'sale':
                values.append(product.name)
                if product.description_sale:
                    values.append(product.description_sale)
            elif line.journal_id.type == 'purchase':
                values.append(product.name)
                if product.description_purchase:
                    values.append(product.description_purchase)
            return '\n'.join(values) if values else False

        term_by_move = (self.move_id.line_ids | self).filtered(
            lambda l: l.display_type == 'payment_term'
        ).sorted(lambda l: l.date_maturity or date.max).grouped('move_id')
        for line in self.filtered(lambda l: l.move_id.inalterable_hash is False):
            if line.display_type == 'payment_term':
                term_lines = term_by_move.get(line.move_id, self.env['account.move.line'])
                n_terms = len(line.move_id.invoice_payment_term_id.line_ids)
                if line.move_id.payment_reference and line.move_id.ref and line.move_id.payment_reference != line.move_id.ref:
                    name = f'{line.move_id.ref} - {line.move_id.payment_reference}'
                elif line.move_id.payment_reference:
                    name = line.move_id.payment_reference
                elif line.move_id.move_type in ['in_invoice', 'in_refund'] and line.move_id.ref:
                    name = line.move_id.ref
                else:
                    name = False

                if n_terms > 1:
                    index = term_lines._ids.index(line.id) if line in term_lines else len(term_lines)
                    name = _('%(name)s installment #%(number)s', name=name if name else '', number=index + 1).lstrip()
                if name:
                    line.name = name
            if not line.product_id or line.display_type in ('line_section', 'line_subsection', 'line_note'):
                continue

            if not line.name or (line._origin and line.product_id != line._origin.product_id):
                line.name = get_name(line)
