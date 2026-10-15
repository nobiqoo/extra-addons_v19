# -*- coding: utf-8 -*-

from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    price_unit_restriction = fields.Boolean(
        string="Price Unit Restriction",
    )

    price_unit_restriction_selection = fields.Selection(
        [('price_unit', 'Price Unit'),
         ('price_list', 'Price list')],
        string='Price Unit Restriction Selection',
    )

    discount_restriction = fields.Boolean(
        string="Discount Restriction",
    )

    maximun_discount_restriction = fields.Float(
        string="Maximun Discount Restriction",
    )
