# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Inherits the model res.config.settings to add the field"""
    _inherit = 'res.config.settings'

    price_unit_restriction = fields.Boolean(
        string="Price Unit Restriction",
        related='company_id.price_unit_restriction',
        readonly=False,
        help='Price Unit Restriction')

    price_unit_restriction_selection = fields.Selection(
        [('price_unit','Price Unit'),
         ('price_list', 'Price list')],
        string='Price Unit Restriction Selection',
        related='company_id.price_unit_restriction_selection',
        readonly=False,
    )

    discount_restriction = fields.Boolean(
        string="Discount Restriction",
        related='company_id.discount_restriction',
        readonly=False,
        help='Discount Restriction')

    maximun_discount_restriction = fields.Float(
        string="Maximun Discount Restriction",
        related='company_id.maximun_discount_restriction',
        readonly=False,
        help='Maximun Discount Restriction'
    )

