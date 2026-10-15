# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    base_calculate = fields.Boolean(
        string='Calculate taxes?',
        default=True,
        help="Automatically calculate base taxes",
    )

    city_id = fields.Many2one('res.city')

    @api.onchange('company_id')
    def onchange_company_id(self):
        if self.move_type in ('out_invoice', 'out_refund'):
            self.city_id = self.company_id.partner_id.city_id

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        if self.move_type in ('in_invoice', 'in_refund'):
            self.city_id = self.partner_id.city_id
        return res

    # @api.onchange(
    #     'company_id',
    #     'partner_id',
    #     'city_id',
    #     'fiscal_position_id',
    # )
    # def _onchange_base_tax(self):
    #     self.calculate_base()

    def calculate_base(self):
        for invoice in self:
            invoice._calculate_base()
            invoice._compute_tax_totals()

    def _calculate_base(self):
        if self.company_id.calculate_ica_by_line:
            return 

        Tax = self.env['account.tax']

        if not self.is_invoice():
            return False
        if self.state != 'draft':
            return False
        if not self.base_calculate:
            return False

        taxes = Tax
        for line in self.invoice_line_ids:
            taxes |= line._get_computed_taxes()

        partner_id = self.is_purchase_document() and self.partner_id or False
        tax_id = taxes.calculate_base(
            self.invoice_line_ids, self.city_id, partner_id
        )

        if tax_id:
            self.invoice_line_ids.tax_ids = tax_id

    @api.onchange('invoice_line_ids', 'city_id')
    def _onchange_quick_edit_line_ids(self):
        self._calculate_base()
        res = super(AccountMove, self)._onchange_quick_edit_line_ids()
        return res


# class AccountMoveLine(models.Model):
#     _inherit = 'account.move.line'

#     @api.onchange(
#         'price_subtotal',
#     )
#     def _onchange_base_tax(self):
#         self.move_id.calculate_base()
