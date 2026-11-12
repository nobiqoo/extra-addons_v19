# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Requerido por el widget analytic_distribution (misma semántica que analytic.mixin)
    analytic_precision = fields.Integer(
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic'),
    )

    fiscalyear_lock_except = fields.Boolean(
        related='company_id.fiscalyear_lock_except',
        readonly=False
    )
    manage_partner_in_invoice_lines_out = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_out',
        readonly=False
    )
    manage_partner_in_invoice_lines_in = fields.Boolean(
        related='company_id.manage_partner_in_invoice_lines_in',
        readonly=False
    )
    account_journal_tax_with_discount_id = fields.Many2one(
        related='company_id.account_journal_tax_with_discount_id',
        string='Cuenta De IVA con Descuento del 100%',
        readonly=False
    )
    account_iva_debit = fields.Many2one(
        related='company_id.account_iva_debit',
        string='Reembolso Iva Productos con Descuento',
        readonly=False
    )
    tax_iva_assumed_id = fields.Many2one(
        related='company_id.tax_iva_assumed_id',
        string='Impuesto IVA Asumido',
        readonly=False
    )
    apply_iva_assumed_on_gift_invoice_lines = fields.Boolean(
        related='company_id.apply_iva_assumed_on_gift_invoice_lines',
        string='Aplicar IVA asumido por defecto en obsequios/promociones',
        readonly=False,
    )
    account_sale_stock_out_expense_id = fields.Many2one(
        related='company_id.account_sale_stock_out_expense_id',
        string='Cuenta gasto salida inventario (obsequios)',
        readonly=False,
    )
    promotion_gift_cogs_analytic_distribution = fields.Json(
        related='company_id.promotion_gift_cogs_analytic_distribution',
        readonly=False,
    )
