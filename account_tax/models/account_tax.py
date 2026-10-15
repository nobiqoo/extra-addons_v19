# -*- coding: utf-8 -*-

from odoo import fields, api, models, Command


class AccountTax(models.Model):
    _inherit = 'account.tax'

    base_city = fields.Boolean(
        string='Base by city?',
        default=False
    )
    base_minimum = fields.Boolean(
        string='Minimum base?',
        default=False
    )
    base_type = fields.Boolean(
        string='Group by city?',
        default=False,
        help='The tax is replaced according to the city.'
    )
    base_value = fields.Float(
        string='Base value',
        digits='Account',
    )

    def compute_base_tax(self, city=False):
        self.ensure_one()

        base_value = self.compute_base_value(city=city)
        base_tax = self.compute_base_city(city)

        return base_value, base_tax

    def compute_base_value(self, city=False):
        self.ensure_one()

        if self.base_city and city:
            if self.tax_scope == 'service':
                return city.base_value_service
            elif self.tax_scope == 'consu':
                return city.base_value_consu
            else:
                return city.base_value

        return self.base_value

    def compute_base_city(self, city):
        self.ensure_one()

        Tax = self.env['account.tax']

        if not self.base_type:
            return self

        partner_id = self.env.context.get('partner_id') \
            or self.env.company.partner_id

        classification_id = partner_id.classification_id

        if not classification_id:
            return Tax

        classification_ids = city.classification_ids.filtered(
            lambda c: c.classification_id.id == classification_id.id)

        return classification_ids and classification_ids.tax_id or Tax

    def calculate_base(self, lines, city_id, partner_id=False):
        if not any(t.base_minimum for t in self):
            return []

        tax_totals = {}
        line_taxes_map = {}

        for line in lines:
            if line._name in ('sale.order.line', 'purchase.order.line'):
                line_taxes_map[line] = line.compute_line_tax()
            elif line._name == 'account.move.line':
                line_taxes_map[line] = line._get_computed_taxes()
            taxes_with_min = line_taxes_map[line].filtered('base_minimum')
            # line_taxes_map[line] = taxes_with_min
            for tax in taxes_with_min:
                tax_totals.setdefault(tax, 0)
                tax_totals[tax] += line.price_subtotal

        for line in lines:
            all_taxes = line_taxes_map[line] # line.product_id.taxes_id
            taxes_with_min = line_taxes_map.get(line, self.env['account.tax']).filtered('base_minimum')

            if not taxes_with_min:
                continue

            # Recordset de impuestos que siempre aplican
            taxes_to_apply = all_taxes - taxes_with_min

            for tax in taxes_with_min:
                total_base = tax_totals.get(tax, 0.0)

                if partner_id:
                    tax = tax.with_context(partner_id=partner_id)

                base_amt, base_tax = tax.compute_base_tax(city=city_id)

                if total_base >= base_amt:
                    taxes_to_apply |= base_tax

            if line._name == 'sale.order.line':
                line.tax_ids = [(6,0, taxes_to_apply.ids)]
            elif line._name == 'purchase.order.line':
                line.tax_ids = [(6, 0, taxes_to_apply.ids)]
            elif line._name == 'account.move.line':
                line.with_context(check_move_validity=False).tax_ids = [(6, 0, taxes_to_apply.ids)]
        return []

    @api.model
    def _compute_taxes_for_single_line(self, base_line, handle_price_include=True, include_caba_tags=False, early_pay_discount_computation=None, early_pay_discount_percentage=None):
        if not base_line['record'] or base_line['record']._name != 'account.move.line':
            return super()._compute_taxes_for_single_line(
                base_line=base_line,
                handle_price_include=handle_price_include,
                include_caba_tags=include_caba_tags,
                early_pay_discount_computation=early_pay_discount_computation,
                early_pay_discount_percentage=early_pay_discount_percentage
            )
        # Determinar el precio base para los impuestos
        # Determinar el tipo de documento
        move_type = base_line['record'].move_id.move_type

        # Determinar el precio base para los impuestos
        if move_type == 'out_invoice' and base_line['discount'] == 100:  # Solo para facturas de cliente
            price_unit_after_discount = base_line['price_unit']  # Ignorar descuento
            # taxes = base_line['taxes'].filtered(lambda t: t.dian_tax_type_id.name == 'IVA')._origin
        else:
            # Cálculo estándar para otros documentos
            price_unit_after_discount = base_line['price_unit'] * (1 - (base_line['discount'] / 100.0))

        taxes = base_line['taxes']._origin

        currency = base_line['currency'] or self.env.company.currency_id
        rate = base_line['rate']

        # Manejo de descuentos por pronto pago, si aplica
        if early_pay_discount_computation in ('included', 'excluded'):
            remaining_part_to_consider = (100 - early_pay_discount_percentage) / 100.0
            price_unit_after_discount = remaining_part_to_consider * price_unit_after_discount

        if taxes:
            taxes_res = taxes.with_context(**base_line['extra_context']).compute_all(
                price_unit_after_discount,  # Usar el precio base determinado arriba
                currency=currency,
                quantity=base_line['quantity'],
                product=base_line['product'],
                partner=base_line['partner'],
                is_refund=base_line['is_refund'],
                handle_price_include=base_line['handle_price_include'],
                include_caba_tags=include_caba_tags,
            )

            if move_type == 'out_invoice' and base_line['discount'] == 100:  # Solo para facturas de cliente
                
                price_unit_after_discount = base_line['price_unit'] * (1 - (base_line['discount'] / 100.0))

                taxes_amount = sum(tax['amount'] for tax in taxes_res.get(' ', []))

                to_update_vals = {
                    'tax_tag_ids': [Command.set(taxes_res['base_tags'])],
                    'price_subtotal': price_unit_after_discount,
                    'price_total': price_unit_after_discount + taxes_amount,
                }
            else:
                
                to_update_vals = {
                    'tax_tag_ids': [Command.set(taxes_res['base_tags'])],
                    'price_subtotal': taxes_res['total_excluded'],
                    'price_total': taxes_res['total_included'],
                }

            tax_values_list = []
            for tax_res in taxes_res['taxes']:
                tax_amount = tax_res['amount'] / rate
                if self.company_id.tax_calculation_rounding_method == 'round_per_line':
                    tax_amount = currency.round(tax_amount)
                tax_rep = self.env['account.tax.repartition.line'].browse(tax_res['tax_repartition_line_id'])
                tax_values_list.append({
                    **tax_res,
                    'tax_repartition_line': tax_rep,
                    'base_amount_currency': tax_res['base'],
                    'base_amount': currency.round(tax_res['base'] / rate),
                    'tax_amount_currency': tax_res['amount'],
                    'tax_amount': tax_amount,
                })

        else:
            price_subtotal = currency.round(price_unit_after_discount * base_line['quantity'])
            to_update_vals = {
                'tax_tag_ids': [Command.clear()],
                'price_subtotal': price_subtotal,
                'price_total': price_subtotal,
            }
            tax_values_list = []

        return to_update_vals, tax_values_list

    def calculate_base_single_line(self, line, city_id, partner_id=False):
        Tax = self.env['account.tax']

        tax_ids = []

        taxes_to_apply = self.filtered(lambda t: t.base_minimum)

        if not taxes_to_apply:
            return tax_ids

        amount_untaxed = line.price_subtotal

        taxes_add = Tax
        taxes_rem = Tax

        for tax in taxes_to_apply:
            if partner_id:
                tax = tax.with_context(partner_id=partner_id)

            base_amount, base_tax = tax.compute_base_tax(city=city_id)

            taxes_rem |= tax
            if tax.amount_type == 'group':
                taxes_rem |= tax.children_tax_ids

            if amount_untaxed >= base_amount:
                taxes_add |= base_tax
            else:
                taxes_rem |= base_tax

        for tax in taxes_rem:
            tax_ids.append((3, tax.id, 0))
        for tax in taxes_add:
            tax_ids.append((4, tax.id, 0))

        return tax_ids
