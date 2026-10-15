# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AccountValuationReportWizard(models.TransientModel):
    _name = 'account.valuation.report.wizard'
    _description = "Wizard Reporte de Valorización"

    product_ids = fields.Many2many(
        comodel_name='product.product',
        string='Productos'
    )
    date_from = fields.Date(
        string='Fecha Inicio'
    )
    date_to = fields.Date(
        string='Fecha Fin'
    )

    def create_report(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError('La fecha final no puede ser menor a la fecha inicio.')
        self.env['account.valuation.report.lines'].search([
            ('user_id', '=', self.env.user.id)]).unlink()
        dict_vals = {}
        domain = []
        if self.product_ids:
            domain.append(('product_id', 'in', self.product_ids.ids))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        valuations = self.env['stock.valuation.layer'].search(domain)
        for valuation in valuations:
            account_income = valuation.product_id.categ_id.property_stock_account_input_categ_id
            order = self.env['purchase.order'].search([
                ('name', '=', valuation.stock_move_id.origin)
            ])
            if order and account_income:
                key = str(order.id) + '-' + str(account_income.id) + str(valuation.product_id.id)
                invoices = order.mapped('order_line.invoice_lines.move_id')
                invoice_lines = self.env['account.move.line'].search([
                    ('move_id', 'in', invoices.ids),
                    ('account_id', '=', account_income.id),
                    ('product_id', '=', valuation.product_id.id),
                    ('parent_state', '=', 'posted')
                ])
                amount_income = sum(
                    [x.debit - x.credit for x in valuation.account_move_id.line_ids.filtered(
                        lambda x: x.account_id.id == account_income.id)])
                amount_invoiced = sum(x.debit - x.credit for x in invoice_lines)

                key = str(order.id) + '-' + str(account_income.id) + str(valuation.product_id.id)
                if key in dict_vals.keys():
                    dict_vals[key]['amount_income'] += amount_income
                    if valuation.account_move_id:
                        dict_vals[key]['moves'].append(valuation.account_move_id.id)
                else:
                    dict_vals[key] = {
                        'order_id': order.id,
                        'product_id': valuation.product_id.id,
                        'account_id': account_income.id,
                        'amount_income': amount_income,
                        'amount_invoiced': amount_invoiced,
                        'user_id': self.env.user.id,
                        'invoice_ids': [(6, 0, invoices.ids)],
                        'moves': [valuation.account_move_id.id] if valuation.account_move_id.id else []
                    }
        for values in dict_vals.values():
            if values['moves']:
                values.update({
                    'move_ids': [(6, 0, values['moves'])],
                })
            del values['moves']
            self.env['account.valuation.report.lines'].create(values)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Informe Valorizado',
            'res_model': 'account.valuation.report.lines',
            'view_mode': 'list,form',
            'domain': [('user_id', '=', self.env.user.id)],
            'target': 'current',
        }
        