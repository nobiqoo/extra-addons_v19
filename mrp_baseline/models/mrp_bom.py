# -*- coding: utf-8 -*-

from odoo import fields, models

SPLIT_METHOD = [
    ('equal', 'Equal'),
    ('by_quantity', 'By Quantity'),
    ('by_current_cost_price', 'By Current Cost'),
    ('by_weight', 'By Weight'),
    ('by_volume', 'By Volume'),
]


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    cost_ids = fields.One2many(
        comodel_name='mrp.bom.cost',
        inverse_name='bom_id',
        string='Costs',
        copy=False
    )


class MrpBomCost(models.Model):
    _name = 'mrp.bom.cost'
    _description = 'BoM Costs'

    account_id = fields.Many2one('account.account')

    bom_id = fields.Many2one(
        comodel_name='mrp.bom',
        ondelete='cascade',
        string='BoM',
        required=True
    )

    price_unit = fields.Float(digits='Product Price')

    product_id = fields.Many2one(
        comodel_name='product.product',
        domain=[('landed_cost_ok', '=', True)]
    )

    split_method = fields.Selection(
        selection=SPLIT_METHOD,
        default='equal'
    )
