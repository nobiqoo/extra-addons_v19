# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.tools import frozendict, format_date, float_compare, Query


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    manage_partner_in_invoice_lines_out = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_out',
    )
    manage_partner_in_invoice_lines_in = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_in',
    )

    @api.depends('tax_ids', 'currency_id', 'partner_id', 'analytic_distribution', 'balance', 'partner_id', 'move_id.partner_id', 'price_unit', 'quantity')
    def _compute_all_tax(self):
        for line in self:
            tax_account = False
            sign = line.move_id.direction_sign
            if line.display_type == 'tax':
                line.compute_all_tax = {}
                line.compute_all_tax_dirty = False
                continue
            if line.display_type == 'product' and line.move_id.is_invoice(True):
                if line.move_id.move_type == 'out_invoice' and line.discount == 100:
                    amount_currency = sign * line.price_unit
                    iva_taxes = line.tax_ids.filtered(
                        lambda tax: tax.dian_tax_type_id and tax.dian_tax_type_id.name == 'IVA'
                    )

                    if iva_taxes:
                        # Reemplazar los impuestos por solo los de IVA
                        line.tax_ids = iva_taxes
                        tax_account = line.move_id.company_id.account_journal_tax_with_discount_id.id
                else:
                    amount_currency = sign * line.price_unit * \
                        (1 - line.discount / 100)
                handle_price_include = True
                quantity = line.quantity
            else:
                amount_currency = line.amount_currency
                handle_price_include = False
                quantity = 1
            compute_all_currency = line.tax_ids.compute_all(
                amount_currency,
                currency=line.currency_id,
                quantity=quantity,
                product=line.product_id,
                partner=line.move_id.partner_id or line.partner_id,
                is_refund=line.is_refund,
                handle_price_include=handle_price_include,
                include_caba_tags=line.move_id.always_tax_exigible,
                fixed_multiplicator=sign,
            )
            rate = line.amount_currency / line.balance if line.balance else 1
            line.compute_all_tax_dirty = True
            line.compute_all_tax = {
                frozendict({
                    'tax_repartition_line_id': tax['tax_repartition_line_id'],
                    'group_tax_id': tax['group'] and tax['group'].id or False,
                    'account_id': tax_account or tax['account_id'] or line.account_id.id,
                    'currency_id': line.currency_id.id,
                    'analytic_distribution': (tax['analytic'] or not tax['use_in_tax_closing']) and line.analytic_distribution,
                    'tax_ids': [(6, 0, tax['tax_ids'])],
                    'tax_tag_ids': [(6, 0, tax['tag_ids'])],
                    'partner_id': line.move_id.partner_id.id or line.partner_id.id,
                    'move_id': line.move_id.id,
                    'display_type': line.display_type,
                }): {
                    'name': tax['name'] + (' ' + _('(Discount)') if line.display_type == 'epd' else ''),
                    'balance': tax['amount'] / rate,
                    'amount_currency': tax['amount'],
                    'tax_base_amount': tax['base'] / rate * (-1 if line.tax_tag_invert else 1),
                }
                for tax in compute_all_currency['taxes']
                if tax['amount']
            }
            if not line.tax_repartition_line_id:
                line.compute_all_tax[frozendict({'id': line.id})] = {
                    'tax_tag_ids': [(6, 0, compute_all_currency['base_tags'])],
                }
