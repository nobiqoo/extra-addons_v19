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
    def _add_tax_details_in_base_line(self, base_line, company, rounding_method=None):
        """
        Override para calcular IVA sobre precio sin descuento cuando hay descuento del 100%
        en facturas de venta, pero manteniendo el subtotal en 0.
        """
        # Verificar si es factura de venta con descuento 100%
        record = base_line.get('record')
        original_discount = None

        if record and record._name == 'account.move.line' \
                and 'account_journal_tax_with_discount_id' in company._fields:
            move = record.move_id
            if move.move_type in ('out_invoice', 'out_refund') and base_line.get('discount') == 100:
                # Guardar descuento original y temporalmente ponerlo en 0 para calcular impuestos
                original_discount = 100
                base_line['discount'] = 0

        if original_discount is None:
            super()._add_tax_details_in_base_line(base_line, company, rounding_method)
            return

        # El "IVA asumido" es un espejo de tasa negativa del IVA real (ver
        # _get_tax_iva_assumed). Si se calculan juntos, Odoo los agrupa en el
        # mismo "batch" de impuestos con precio incluido (mismo amount_type/
        # price_include/include_base_amount) y, como sus tasas suman 0%
        # (ej. 19% + -19%), el motor no extrae nada del precio: usa el precio
        # bruto como base y el IVA real queda sobrevalorado (sobre 7500 con
        # IVA 19% incluido calcularía 1425 en vez de los 1197.48 correctos).
        # Por eso el IVA real se calcula aislado del asumido, y el asumido se
        # agrega después como el espejo exacto del IVA ya bien calculado.
        all_taxes = base_line['tax_ids']
        real_taxes = all_taxes.filtered(
            lambda t: t.dian_tax_type_id and t.dian_tax_type_id.name == 'IVA')
        assumed_taxes = all_taxes - real_taxes

        if real_taxes and assumed_taxes:
            base_line['tax_ids'] = real_taxes
            super()._add_tax_details_in_base_line(base_line, company, rounding_method)
            base_line['tax_ids'] = all_taxes

            tax_details = base_line['tax_details']
            for assumed_tax in assumed_taxes:
                for tax_data in list(tax_details['taxes_data']):
                    if tax_data['tax'].tax_group_id != assumed_tax.tax_group_id:
                        continue
                    mirrored = dict(tax_data, tax=assumed_tax, batch=assumed_tax)
                    for field in ('tax_amount', 'raw_tax_amount', 'raw_tax_amount_currency'):
                        mirrored[field] = -mirrored[field]
                    tax_details['taxes_data'].append(mirrored)
                    break
        else:
            # Patrón inesperado (sin IVA detectable, o sin impuesto asumido):
            # se conserva el comportamiento anterior calculando todo junto.
            super()._add_tax_details_in_base_line(base_line, company, rounding_method)
            tax_details = base_line['tax_details']

        # Restaurar el descuento original
        base_line['discount'] = original_discount
        # Marcar que tiene descuento 100% para uso posterior
        base_line['has_100_discount'] = True

        # El subtotal debe ser 0 por el descuento 100% (el precio sin
        # descuento solo se usa para calcular la base gravable del IVA).
        tax_details['raw_total_excluded_currency'] = 0.0
        tax_details['raw_total_excluded'] = 0.0
    
    @api.model
    def _add_accounting_data_to_base_line_tax_details(self, base_line, company, include_caba_tags=False):
        """
        Override para modificar la cuenta contable del IVA cuando hay descuento del 100%
        en facturas de venta.
        """
        # Llamar al super para que haga el cálculo normal
        super()._add_accounting_data_to_base_line_tax_details(base_line, company, include_caba_tags)
        
        # Verificar si es factura de venta con descuento 100%
        has_100_discount = base_line.get('has_100_discount', False)
        
        if not has_100_discount:
            return

        # Las cuentas especiales las define account_baseline (dependencia
        # opcional); sin ese módulo el campo no está en el registry.
        if 'account_journal_tax_with_discount_id' not in company._fields:
            return

        # Obtener las cuentas especiales configuradas
        acc_tax_iva = company.account_journal_tax_with_discount_id
        acc_tax_iva_assumed = company.account_iva_debit
        tax_iva_assumed_configured = company.tax_iva_assumed_id

        if not acc_tax_iva:
            return
        
        # Modificar la cuenta del IVA en tax_details
        tax_details = base_line.get('tax_details', {})
        for tax_data in tax_details.get('taxes_data', []):
            tax = tax_data['tax']
            
            # Verificar si es un impuesto IVA
            is_iva = tax.dian_tax_type_id and tax.dian_tax_type_id.name == 'IVA'

            # Verificar si es el impuesto IVA asumido configurado
            is_iva_assumed = tax_iva_assumed_configured and tax.id == tax_iva_assumed_configured.id

            for tax_rep_data in tax_data.get('tax_reps_data', []):
                # Si es el IVA asumido configurado, usar la cuenta de reembolso
                if is_iva_assumed and acc_tax_iva_assumed:
                    tax_rep_data['account'] = acc_tax_iva_assumed
                    tax_rep_data['grouping_key']['account_id'] = acc_tax_iva_assumed.id

                # Si es IVA normal, usar la cuenta especial de IVA con descuento
                elif is_iva and not is_iva_assumed:
                    tax_rep_data['account'] = acc_tax_iva
                    tax_rep_data['grouping_key']['account_id'] = acc_tax_iva.id

    def _get_city_tax_candidates(self):
        """Impuestos que alguna ciudad pueda haber asignado para el CIIU vigente.

        Cada ciudad mapea el CIIU del socio a un impuesto distinto (o a
        ninguno) en res.city.classification. Al cambiar de ciudad hay que
        conocer todo ese universo, no solo el de la ciudad elegida ahora,
        para poder retirar el impuesto que dejó una ciudad anterior aunque la
        nueva no tenga nada configurado.
        """
        self.ensure_one()
        if not self.base_type:
            return self.env['account.tax']

        partner_id = self.env.context.get('partner_id') \
            or self.env.company.partner_id
        classification_id = partner_id.classification_id

        if not classification_id:
            return self.env['account.tax']

        return self.env['res.city.classification'].search([
            ('company_id', '=', self.env.company.id),
            ('classification_id', '=', classification_id.id),
        ]).tax_id

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
            # Retira el impuesto de una ciudad anterior aunque la ciudad
            # vigente no tenga ninguno configurado (ver _get_city_tax_candidates).
            taxes_rem |= tax._get_city_tax_candidates()

            if amount_untaxed >= base_amount:
                taxes_add |= base_tax
            else:
                taxes_rem |= base_tax

        for tax in taxes_rem - taxes_add:
            tax_ids.append((3, tax.id, 0))
        for tax in taxes_add:
            tax_ids.append((4, tax.id, 0))

        return tax_ids
