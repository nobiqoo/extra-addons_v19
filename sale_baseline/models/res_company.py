# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    salesperson_not_editable = fields.Boolean(
        'Salesperson field not editable',
        help='Allows to restrict the edition of the '
        'salesperson field in sales and invoices.'
    )
    add_tag_to_non_buyers = fields.Boolean(
        'Add tag to non buyers and block them',
        help='Allows you to add a tag and block to the customer who '
        'has not purchased in the last few months.'
    )
    months_without_buying = fields.Integer(
        'Months without buyings',
        help='months required to add tag.'
    )
    tags_to_add_ids = fields.Many2one(
        'res.partner.category',
        'Tag'
    )

    sale_confirm_quantity = fields.Boolean(
        string='Do not confirm without quantity',
        default=False,
        help='It does not allow to confirm the sales order '
        'if there are no quantities available.',
    )

    allow_confirm_sale_for_administrators = fields.Boolean(
        string="Allow confirm sale for administrators",
        default=False,
        help='Only users belonging to the Sale / Administrator group are allowed to confirm orders.',
    )
    block_expired_invoice = fields.Boolean(
        'Block expired invoice',
        help='Validate if the partner has overdue '
        'invoices and block the current invoice.'
    )
    block_credit_limit = fields.Boolean(
        'Block by credit limit',
        help='Validate if the partner has not paid invoices '
        'and the amount exceeds the credit limit.'
    )

    restriction_line_price = fields.Boolean(
        'Restrict product line price edition.',
        help='Gives access to groups to be able to '
        'edit the price of the lines of an order. '
    )

    show_price_variant_ldp = fields.Many2one('product.pricelist',
                                             'Price list to show in variants',
                                             help='Select the price list you want to display in product variant views')
    day_limit_invoice_block = fields.Integer(
        string=_('Day limit invoice'),
        help=_('Day limit invoice'),
        default=0,
    )
