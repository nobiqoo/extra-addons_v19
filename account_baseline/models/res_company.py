# -*- coding: utf-8 -*-

from odoo import _, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    fiscalyear_lock_except = fields.Boolean(
        'Lock Date Exception',
        help='Allows block dates when there are draft seats.'
    )
    manage_partner_in_invoice_lines_out = fields.Boolean(
        'Manage partner in sales invoice lines',
        help='Allows to change the partner from the sales invoice lines and '
        'these will be assigned to the account income and '
        'the partner in the header will be assigned to the '
        'account receivable.'
    )
    manage_partner_in_invoice_lines_in = fields.Boolean(
        'Manage partner in supplier invoice lines',
        help='Allows to change the partner from the supplier invoice lines and '
        'these will be assigned to the account expense and '
        'the partner in the header will be assigned to the '
        'account payable.'
    )

    close_date_validation = fields.Boolean(
        string="Remove validation in account close dates", default=False)
    hide_credit_note_fully_credited = fields.Boolean(
        string='Hide credit note button on fully credited invoices',
        help='Hides the "Credit Note" button on customer invoices and vendor bills whose posted '
             'credit notes already cover the invoice total. If unchecked, the native flow is kept.',
    )
    account_journal_tax_with_discount_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta De IVA con Descuento del 100%',
    )
    account_iva_debit = fields.Many2one(
        comodel_name='account.account',
        string='Reembolso Iva Productos con Descuento',
    )
    tax_iva_assumed_id = fields.Many2one(
        comodel_name='account.tax',
        string='Impuesto IVA Asumido',
        help='Impuesto que se aplica cuando hay descuento del 100%. '
             'Debe ser un impuesto negativo que compense el IVA del producto obsequiado.',
        domain="[('type_tax_use', '=', 'sale'), ('company_id', '=', id), ('amount', '<', 0), ('active', '=', True)]",
    )
    apply_iva_assumed_on_gift_invoice_lines = fields.Boolean(
        string='Aplicar IVA asumido por defecto en obsequios/promociones',
        default=False,
        help='Solo aplica al crear la factura desde la orden de venta: si está activo, en líneas con '
             'descuento 100 % se omiten los impuestos copiados del pedido para forzar el recálculo '
             '(IVA + IVA asumido). El onchange en facturas no usa este campo: con 100 % se añade '
             'IVA asumido; con descuento distinto de 100 % no.',
    )
    account_sale_stock_out_expense_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta de gasto salida inventario (obsequios)',
        help='Para líneas de factura de venta con importe cero o descuento 100 % (obsequio) y '
             'valoración perpetua: el débito COGS usa esta cuenta de gasto en lugar de la cuenta '
             'de costo del producto. Dejar vacío para usar siempre la cuenta de costo estándar.',
        domain="[('account_type', 'in', ('expense', 'expense_other')), "
               "('company_ids', 'parent_of', id)]",
    )
    promotion_gift_cogs_analytic_distribution = fields.Json(
        string='Analítica COGS obsequios (opcional)',
        help='Si se informa, sustituye la distribución analítica del apunte de gasto COGS en '
             'líneas obsequio/promoción (importe cero), separando la analítica del ingreso. '
             'Si se deja vacío, se mantiene la analítica de la línea de factura.',
    )
