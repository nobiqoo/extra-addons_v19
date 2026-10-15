# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _


class AccountValuationReportLines(models.Model):
    _name = "account.valuation.report.lines"
    _description = "Líneas de Reporte de Valorización"

    order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Orden de Compra',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto'
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta'
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Usuario'
    )
    invoice_ids = fields.Many2many(
        relation='account_invoice_valuation_rel',
        comodel_name='account.move',
        string='Facturas'
    )
    move_ids = fields.Many2many(
        relation='account_move_valuation_rel',
        comodel_name='account.move',
        string='Movimientos'
    )
    amount_income = fields.Float(
        string='Valor Valorización',
    )
    amount_invoiced = fields.Float(
        string='Valor Facturado'
    )
    amount_difference = fields.Float(
        string='Diferencia',
        compute='_compute_amount_difference',
        store=True
    )

    @api.depends('amount_income', 'amount_invoiced')
    def _compute_amount_difference(self):
        for record in self:
            record.amount_difference = record.amount_invoiced + record.amount_income