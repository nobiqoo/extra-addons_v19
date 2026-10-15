# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    base_calculate = fields.Boolean(
        string='Calculate taxes?',
        default=True,
        help="Automatically calculate base taxes",
    )

    city_id = fields.Many2one('res.city')

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        res = super(PurchaseOrder, self).onchange_partner_id()
        self.city_id = self.partner_id.city_id
        return res

    def button_confirm(self):
        self.calculate_base()
        return super(PurchaseOrder, self).button_confirm()

    # @api.onchange(
    #     'partner_id',
    #     'fiscal_position_id',
    # )
    # def _onchange_base_tax(self):
    #     self.calculate_base()

    def calculate_base(self):
        for purchase in self:
            purchase._calculate_base()

    def _calculate_base(self):
        Tax = self.env['account.tax']

        if self.state in ('done', 'cancel'):
            return False
        if not self.base_calculate:
            return False

        taxes = Tax
        for line in self.order_line:
            taxes |= line.compute_line_tax()

        taxes_id = taxes.calculate_base(
            self.order_line, self.city_id, self.partner_id
        )
        if taxes_id:
            self.order_line.tax_ids = taxes_id
            # self.order_line.write({'tax_ids': taxes_id})

    def _prepare_invoice(self):
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()
        invoice_vals.update({
            'base_calculate': self.base_calculate,
            'city_id': self.city_id and self.city_id.id or False
        })
        return invoice_vals

    @api.onchange('order_line', 'city_id')
    def _onchange_order_line_ids(self):
        self._calculate_base()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # @api.onchange(
    #     'price_subtotal',
    # )
    # def _onchange_base_tax(self):
    #     if self.price_subtotal:
    #         self.order_id.calculate_base()

    def compute_line_tax(self):
        line = self.with_company(self.company_id)
        fpos = line.order_id.fiscal_position_id or line.order_id.fiscal_position_id._get_fiscal_position(
            line.order_id.partner_id
        )
        taxes = line.product_id.supplier_taxes_id.filtered(
            lambda r: r.company_id == line.env.company
        )
        return fpos.map_tax(taxes)
