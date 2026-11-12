from markupsafe import Markup

from odoo import models
from odoo.tools import html_sanitize
from odoo.tools.float_utils import float_compare, float_is_zero


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _arthome_expand_lot_rows(self, rows, currency):
        """Expand presentation only when delivered lot quantities reconcile.

        Shared deliveries are consumed once across invoice lines. Partial
        invoices remain grouped: the sale link alone cannot identify which
        particular rolls were invoiced. No proportional lot quantity is invented.
        """
        groups = {}
        for index, row in enumerate(rows):
            line = row['line']
            if (line.display_type != 'product' or line.product_id.type == 'service'
                    or not line.product_id.arthome_split_invoice_lots or line.quantity <= 0):
                continue
            moves = line._get_related_picking_lines().filtered(
                lambda move: move.state == 'done' and move.product_id == line.product_id
                and (
                    (move.location_id.usage == 'customer' and move.location_dest_id.usage != 'customer')
                    if self.move_type == 'out_refund' else
                    (move.location_dest_id.usage == 'customer' and move.location_id.usage != 'customer')
                )
            )
            operations = moves.move_line_ids.filtered(
                lambda operation: operation.product_id == line.product_id
                and operation.lot_id in row['lots'] and operation.quantity > 0
            ).sorted('id')
            if not operations:
                continue
            key = (tuple(operations.ids), line.product_uom_id.id)
            group = groups.setdefault(key, {'rows': [], 'quantities': {}})
            group['rows'].append(index)
            if not group['quantities']:
                for operation in operations:
                    lot = operation.lot_id
                    quantity = operation.product_uom_id._compute_quantity(
                        operation.quantity, line.product_uom_id, round=False,
                    )
                    group['quantities'][lot] = group['quantities'].get(lot, 0.0) + quantity

        expanded = {}
        # Different links to overlapping deliveries cannot safely allocate lots.
        for key, group in groups.items():
            if any(set(key[0]) & set(other[0]) for other in groups if other != key):
                continue
            indexes = group['rows']
            precision = rows[indexes[0]]['line'].product_uom_id.rounding
            invoiced = sum(rows[index]['quantity'] for index in indexes)
            delivered = sum(group['quantities'].values())
            if float_compare(invoiced, delivered, precision_rounding=precision):
                continue
            pool = [[lot, quantity] for lot, quantity in group['quantities'].items()]
            pool[-1][1] += invoiced - delivered  # Only a UoM rounding remainder.
            cursor = 0
            for index in indexes:
                row = rows[index]
                remaining = row['quantity']
                parts = []
                while not float_is_zero(remaining, precision_rounding=precision) and cursor < len(pool):
                    lot, available = pool[cursor]
                    quantity = min(remaining, available)
                    if quantity > 0:
                        parts.append(dict(row, lots=lot, quantity=quantity))
                        remaining -= quantity
                        pool[cursor][1] -= quantity
                    if float_is_zero(pool[cursor][1], precision_rounding=precision):
                        cursor += 1
                if parts:
                    # Preserve line subtotal, including discount/tax-included
                    # pricing and currency rounding; reconcile on the last roll.
                    parts[-1]['quantity'] += remaining
                    allocated = 0.0
                    for part in parts[:-1]:
                        part['subtotal'] = currency.round(row['subtotal'] * part['quantity'] / row['quantity'])
                        allocated += part['subtotal']
                    parts[-1]['subtotal'] = row['subtotal'] - allocated
                    expanded[index] = parts
        return [part for index, row in enumerate(rows) for part in expanded.get(index, [row])]

    def _arthome_report_values(self):
        """Use accounting balances for the company-currency representation."""
        self.ensure_one()
        is_credit = self.move_type == 'out_refund'
        is_note = is_credit or self.type_note == 'debit'
        balance_sign = 1 if is_credit else -1
        currency = self.company_currency_id
        foreign = self.currency_id != currency
        dual_currency = self.currency_id.name == 'USD' and currency.name == 'COP'
        lines = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        rows = []
        discount = 0.0
        for line in self.invoice_line_ids.sorted(lambda line: (line.sequence, line.id)):
            if line.display_type != 'product':
                rows.append({'line': line})
                continue
            # balance already incorporates the invoice's historical exchange rate.
            subtotal = balance_sign * line.balance if foreign else line.price_subtotal
            rate = 1 / self.invoice_currency_rate if foreign and self.invoice_currency_rate else 1
            unit = line.price_unit * rate
            if line.discount:
                undiscounted = line.tax_ids.compute_all(
                    line.price_unit, currency=self.currency_id, quantity=line.quantity,
                    product=line.product_id, partner=self.partner_id,
                    is_refund=is_credit,
                )['total_excluded']
                discount += currency.round((undiscounted - line.price_subtotal) * rate)
            rows.append({
                'line': line,
                'lots': line.lot_ids,
                'quantity': line.quantity,
                'subtotal': line.price_subtotal if dual_currency else subtotal,
                'unit': line.price_unit if dual_currency else unit,
            })
        base = sum(balance_sign * line.balance if foreign else line.price_subtotal for line in lines)
        taxes = {}
        tax_rows = {}
        accounting_tax_total = 0.0
        for line in self.line_ids.filtered('tax_line_id'):
            accounting_tax_total += balance_sign * line.balance
            # ZY identifies the self-withholding and its counterpart in the
            # Colombian localization. Hide both only in the printed report.
            if line.tax_line_id.dian_tax_type_id.dian_code == 'ZY':
                continue
            group = line.tax_line_id.tax_group_id
            taxes[group.name] = taxes.get(group.name, 0.0) + balance_sign * line.balance
            row = tax_rows.setdefault(group.id, {'name': group.name, 'cop': 0.0, 'usd': 0.0})
            row['cop'] += balance_sign * line.balance
            row['usd'] += balance_sign * line.amount_currency
        total = -balance_sign * self.amount_total_signed
        adjustment = currency.round(total - base - accounting_tax_total)
        if adjustment:
            taxes['Otros ajustes'] = adjustment
        usd_adjustment = self.currency_id.round(
            self.amount_total - self.amount_untaxed
            - balance_sign * sum(self.line_ids.filtered('tax_line_id').mapped('amount_currency'))
        )
        if adjustment or usd_adjustment:
            tax_rows['adjustment'] = {'name': 'Otros ajustes', 'cop': adjustment, 'usd': usd_adjustment}
        return {
            'rows': self._arthome_expand_lot_rows(rows, self.currency_id if dual_currency else currency),
            'currency': currency, 'foreign': foreign,
            'dual_currency': dual_currency,
            'is_note': is_note,
            'document_title': ('NOTA CRÉDITO ELECTRÓNICA' if is_credit else
                               'NOTA DÉBITO ELECTRÓNICA' if is_note else
                               'FACTURA ELECTRÓNICA DE VENTA'),
            'uuid_label': 'CUDE' if is_note else 'CUFE',
            'reference_name': self.name_ei_ref or self.reversed_entry_id.name,
            'reference_date': self.issue_date_ei_ref or self.reversed_entry_id.invoice_date,
            'reference_uuid': self.uuid_ei_ref or self.reversed_entry_id.fe_cufe_cude_ref,
            'trm': 1 / self.invoice_currency_rate if self.invoice_currency_rate else 0,
            'tax_rows': list(tax_rows.values()),
            'gross': base + discount, 'discount': discount, 'base': base,
            'tributary': Markup(html_sanitize(self.company_id.tributary_information or '')),
            'resolution': Markup(html_sanitize(self.journal_id.resolution_text or '')),
            'legal': Markup(html_sanitize(self.journal_id.note_ei or '')),
            'taxes': list(taxes.items()), 'total': total,
            'quantity': sum(lines.filtered(lambda line: line.product_id.type != 'service').mapped('quantity')),
            'orders': ', '.join(self.invoice_line_ids.sale_line_ids.order_id.mapped('name')),
            'references': ', '.join(filter(None, self.invoice_line_ids.sale_line_ids.order_id.mapped('client_order_ref'))),
        }
