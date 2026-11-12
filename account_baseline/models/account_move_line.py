# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _is_promotion_gift_line(self):
        """Línea de producto en venta considerada obsequio/promoción (importe cero en factura)."""
        self.ensure_one()
        if self.display_type != 'product' or not self.move_id:
            return False
        if not self.move_id.is_sale_document(include_receipts=True):
            return False
        if float_compare(self.discount or 0.0, 100.0, precision_digits=4) >= 0:
            return True
        currency = self.currency_id or self.move_id.currency_id
        if currency:
            if currency.is_zero(self.price_subtotal or 0.0):
                return True
            if currency.is_zero(self.price_total or 0.0):
                return True
        return False

    manage_partner_in_invoice_lines_out = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_out',
    )
    manage_partner_in_invoice_lines_in = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_in',
    )

    @api.constrains('account_id', 'display_type')
    def _check_payable_receivable(self):
        for line in self:
            account_type = line.account_id.account_type
            move = line.move_id

            # Verificar si la factura tiene todas las líneas con 100% de descuento
            all_discounted = all(
                l.discount == 100 for l in move.invoice_line_ids) if move.move_type == 'out_invoice' else False

            # Solo aplicamos la validación si no todas las líneas tienen 100% de descuento
            if not all_discounted:
                if move.is_sale_document(include_receipts=True):
                    if account_type == 'liability_payable':
                        raise UserError(
                            _("La cuenta %s es de tipo por pagar, pero se está utilizando en una operación de venta.", line.account_id.code))
                    if (line.display_type == 'payment_term') ^ (account_type == 'asset_receivable'):
                        raise UserError(
                            _("Cualquier apunte contable en una cuenta por cobrar debe tener una fecha límite y viceversa."))

                if move.is_purchase_document(include_receipts=True):
                    if account_type == 'asset_receivable':
                        raise UserError(
                            _("La cuenta %s es de tipo por cobrar, pero se está utilizando en una operación de compra.", line.account_id.code))
                    if (line.display_type == 'payment_term') ^ (account_type == 'liability_payable'):
                        raise UserError(
                            _("Cualquier apunte contable en una cuenta por pagar debe tener una fecha límite y viceversa."))

    def _get_repartition_lines_iva_assumed(self):
        if not self.company_id.account_iva_debit:
            raise UserError(
                _("No se ha configurado la cuenta de 'Reembolso Iva Productos con Descuento' en la compañía."))
        invoice_repartition_lines = [
            {'repartition_type': 'base',
             'document_type': 'invoice',
             'account_id': False},
            {'repartition_type': 'tax',
             'document_type': 'invoice',
             'account_id': self.company_id.account_iva_debit.id},
        ]
        refund_repartition_lines = [
            {'repartition_type': 'base',
             'document_type': 'refund',
             'account_id': False},
            {'repartition_type': 'tax',
             'document_type': 'refund',
             'account_id': self.company_id.account_iva_debit.id},
        ]

        return invoice_repartition_lines, refund_repartition_lines

    def _get_tax_iva_assumed(self, iva_taxes):
        """
        Obtener impuesto 'IVA asumido' configurado en la compañía.
        Si no está configurado, se busca o crea automáticamente por criterios técnicos.
        """
        # Usar el impuesto configurado en la compañía (prioridad) si está activo
        # Se comenta porque no es funcional porque esto asume una sola tasa de IVA asumido, 
        # pero puede haber varias según el grupo de impuestos y la tasa de IVA.
        # if self.company_id.tax_iva_assumed_id and self.company_id.tax_iva_assumed_id.active:
        #     return self.company_id.tax_iva_assumed_id
        
        # Si no está configurado, buscarlo por criterios técnicos
        iva_assumed = self.env['account.tax'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('amount', '=', -iva_taxes.amount),
            ('tax_group_id', '=', iva_taxes.tax_group_id.id),
            ('type_tax_use', '=', 'sale'),
            ('active', '=', True),
        ], limit=1)
        
        if iva_assumed:
            return iva_assumed
        
        # No existe, crearlo
        invoice_repartition_lines, refund_repartition_lines = self._get_repartition_lines_iva_assumed()
        iva_assumed = self.env['account.tax'].create({
            'name': 'IVA asumido',
            'dian_tax_type_id': self.env.ref('l10n_co_data_bloodo.tax_type_15').id,
            'amount': -iva_taxes.amount,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_group_id': iva_taxes.tax_group_id.id,
            'sequence': 1000,
            'price_include_override': iva_taxes.price_include_override,
            'company_id': self.company_id.id,
            'invoice_repartition_line_ids': [(0, 0, x) for x in invoice_repartition_lines],
            'refund_repartition_line_ids': [(0, 0, x) for x in refund_repartition_lines],
        })
        return iva_assumed

    def _get_computed_taxes(self):
        # IVA asumido en factura: solo según descuento (100 % sí, distinto no). No usar
        # apply_iva_assumed_on_gift_invoice_lines aquí; ese flag solo aplica en sale.order.line.
        res = super(AccountMoveLine, self)._get_computed_taxes()
        if self.move_id.move_type in ('out_invoice', 'out_refund'):
            if self.display_type == 'product' and float_compare(
                    self.discount or 0.0, 100.0, precision_digits=4) >= 0:
                iva_assumed = self.env['account.tax']
                taxes = res
                iva_taxes = taxes.filtered(
                    lambda tax: tax.dian_tax_type_id and tax.dian_tax_type_id.name == 'IVA'
                    and tax.amount
                    )
                if not iva_taxes:
                    # El impuesto calculado para esta línea (posición fiscal del
                    # cliente, edición manual previa, etc.) quedó en "No aplica
                    # IVA" (0%). Para un obsequio/muestra debe tomarse el IVA
                    # propio del producto, ignorando esa exención puntual.
                    iva_taxes = self.product_id.taxes_id.filtered(
                        lambda tax: tax.company_id == self.company_id
                        and tax.dian_tax_type_id and tax.dian_tax_type_id.name == 'IVA'
                        and tax.amount
                        )
                if iva_taxes:
                    iva_assumed = self._get_tax_iva_assumed(iva_taxes)
                res = iva_taxes | iva_assumed
        return res

    @api.depends('product_id', 'product_uom_id', 'discount')
    def _compute_tax_ids(self):
        return super(AccountMoveLine, self)._compute_tax_ids()

    def _get_refund_account(self):
        """Cuenta de devolución del producto (o de su categoría) mapeada por la posición fiscal."""
        self.ensure_one()
        accounts = self.with_company(self.company_id).product_id.product_tmpl_id.get_product_accounts(
            fiscal_pos=self.move_id.fiscal_position_id)
        return accounts.get('refund') or self.env['account.account']

    def _compute_account_id(self):
        super()._compute_account_id()
        # Notas crédito de cliente creadas directamente: el core siempre pone la cuenta de ingresos
        refund_lines = self.filtered(
            lambda l: l.display_type == 'product' and l.product_id and l.move_id.move_type == 'out_refund')
        for line in refund_lines:
            refund_account = line._get_refund_account()
            if refund_account:
                line.account_id = refund_account
