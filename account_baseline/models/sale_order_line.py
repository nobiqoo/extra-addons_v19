# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        """Solo OV→factura: si la compañía lo activa y la línea va al 100 %, quita tax_ids para recalcular.

        No afecta al onchange de líneas en facturas (eso lo resuelve account.move.line._get_computed_taxes).
        """
        res = super()._prepare_invoice_line(**optional_values)
        if (
            self.company_id.apply_iva_assumed_on_gift_invoice_lines
            and float_compare(self.discount or 0.0, 100.0, precision_digits=4) >= 0
        ):
            res.pop('tax_ids', None)
        return res

    def _get_tax_iva_assumed(self, iva_taxes):
        """Espejo de account.move.line._get_tax_iva_assumed: localiza o crea el
        impuesto 'IVA asumido' correspondiente, para reflejarlo ya en la orden
        de venta y no solo al facturar."""
        iva_assumed = self.env['account.tax'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('amount', '=', -iva_taxes.amount),
            ('tax_group_id', '=', iva_taxes.tax_group_id.id),
            ('type_tax_use', '=', 'sale'),
            ('active', '=', True),
        ], limit=1)
        if iva_assumed:
            return iva_assumed

        if not self.company_id.account_iva_debit:
            raise UserError(
                _("No se ha configurado la cuenta de 'Reembolso Iva Productos con Descuento' en la compañía."))

        invoice_repartition_lines = [
            {'repartition_type': 'base', 'document_type': 'invoice', 'account_id': False},
            {'repartition_type': 'tax', 'document_type': 'invoice', 'account_id': self.company_id.account_iva_debit.id},
        ]
        refund_repartition_lines = [
            {'repartition_type': 'base', 'document_type': 'refund', 'account_id': False},
            {'repartition_type': 'tax', 'document_type': 'refund', 'account_id': self.company_id.account_iva_debit.id},
        ]
        return self.env['account.tax'].create({
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

    @api.depends('discount')
    def _compute_tax_ids(self):
        # Mismo criterio que account.move.line._get_computed_taxes(): con
        # descuento 100 % (obsequio/muestra) la línea debe mostrar ya el IVA
        # de muestrario + su IVA asumido, no esperar a la factura.
        super()._compute_tax_ids()
        for line in self:
            if line.display_type or not line.product_id:
                continue
            if not line.company_id.apply_iva_assumed_on_gift_invoice_lines:
                continue
            if float_compare(line.discount or 0.0, 100.0, precision_digits=4) < 0:
                continue
            iva_taxes = line.tax_ids.filtered(
                lambda tax: tax.dian_tax_type_id and tax.dian_tax_type_id.name == 'IVA' and tax.amount
            )
            if not iva_taxes:
                # El impuesto calculado (posición fiscal, edición manual previa,
                # etc.) quedó en "No aplica IVA" (0 %): se toma el IVA propio
                # del producto, ignorando esa exención puntual.
                iva_taxes = line.product_id.taxes_id.filtered(
                    lambda tax: tax.company_id == line.company_id
                    and tax.dian_tax_type_id and tax.dian_tax_type_id.name == 'IVA' and tax.amount
                )
            iva_assumed = self.env['account.tax']
            if iva_taxes:
                iva_assumed = line._get_tax_iva_assumed(iva_taxes)
            line.tax_ids = iva_taxes | iva_assumed
