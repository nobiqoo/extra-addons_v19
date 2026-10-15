# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    base_calculate = fields.Boolean(
        string='Calculate taxes?',
        default=True,
        help="Automatically calculate base taxes",
    )

    city_id = fields.Many2one('res.city')

    @api.onchange('company_id')
    def onchange_company_id(self):
        self.city_id = self.company_id.partner_id.city_id

    def action_confirm(self):
        if self.company_id.calculate_ica_by_line:
            for line in self.order_line:
                line._onchange_city_or_subtotal()
        else:
            self.calculate_base()
        return super(SaleOrder, self).action_confirm()

    # @api.onchange(
    #     'company_id',
    #     'fiscal_position_id',
    # )
    # def _onchange_base_tax(self):
    #     self.calculate_base()

    def calculate_base(self):
        if self.company_id.calculate_ica_by_line:
            return
        for sale in self:
            sale._calculate_base()

    def _calculate_base(self):
        if self.company_id.calculate_ica_by_line:
            return
        Tax = self.env['account.tax']

        if self.state in ('done', 'cancel'):
            return False
        if not self.base_calculate:
            return False

        taxes = Tax
        for line in self.order_line:
            taxes |= line.compute_line_tax()

        tax_id = taxes.calculate_base(self.order_line, self.city_id, self.partner_id)
        if tax_id:
            self.order_line.tax_id = tax_id

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals.update({
            'base_calculate': self.base_calculate,
            'city_id': self.city_id and self.city_id.id or False
        })
        return invoice_vals

    @api.onchange('order_line', 'city_id')
    def _onchange_order_line_ids(self):
        if not self.company_id.calculate_ica_by_line:
            self._calculate_base()
