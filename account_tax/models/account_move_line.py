# -*- coding: utf-8 -*-
from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    city_id = fields.Many2one(
        'res.city',
        string="Ciudad"
    )

    @api.onchange('product_id')
    def _onchange_city_id(self):
        self.city_id = self.move_id.city_id


    @api.onchange('city_id', 'price_subtotal')
    def _onchange_city_or_subtotal(self):

        move = self.move_id
        if move and not move.company_id.calculate_ica_by_line:
            return

        if not self.move_id or not self.city_id:
            return

        if not self.move_id.is_invoice():
            return

        Tax = self.env['account.tax']
        taxes = Tax
        taxes |= self._get_computed_taxes() 
        partner_id = self.move_id.is_purchase_document() and self.move_id.partner_id or False
        applicable_taxes = taxes.calculate_base_single_line(
            line=self,
            city_id=self.city_id,
            partner_id=partner_id
        )

        self.tax_ids = applicable_taxes