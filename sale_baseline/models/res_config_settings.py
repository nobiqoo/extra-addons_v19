# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    salesperson_not_editable = fields.Boolean(
        'Salesperson field not editable',
        related='company_id.salesperson_not_editable',
        readonly=False
    )
    add_tag_to_non_buyers = fields.Boolean(
        'Add tag to non buyers and block them',
        related='company_id.add_tag_to_non_buyers',
        readonly=False
    )
    months_without_buying = fields.Integer(
        'Months',
        related='company_id.months_without_buying',
        readonly=False
    )
    tags_to_add_ids = fields.Many2one(
        'res.partner.category',
        'Tag',
        related='company_id.tags_to_add_ids',
        readonly=False
    )

    sale_confirm_quantity = fields.Boolean(
        related='company_id.sale_confirm_quantity',
        readonly=False
    )

    allow_confirm_sale_for_administrators = fields.Boolean(
        related='company_id.allow_confirm_sale_for_administrators',
        readonly=False
    )
    block_expired_invoice = fields.Boolean(
        related='company_id.block_expired_invoice',
        readonly=False
    )
    block_credit_limit = fields.Boolean(
        related='company_id.block_credit_limit',
        readonly=False
    )

    restriction_line_price = fields.Boolean(
        related='company_id.restriction_line_price',
        readonly=False
    )
    show_price_variant_ldp = fields.Many2one(
        related='company_id.show_price_variant_ldp',
        help='Select the price list you want to display in product variant views',
        readonly=False)
    day_limit_invoice_block = fields.Integer(
        string=_('Day limit invoice'),
        related='company_id.day_limit_invoice_block',
        readonly=False
    )
