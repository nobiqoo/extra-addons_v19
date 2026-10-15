# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    purchase_import_tariff = fields.Selection(
        selection=[("tariff", "Tax"), ("invoice", "Invoice")], default="tariff"
    )

    purchase_import_freight = fields.Selection(
        selection=[("freight", "Freight"), ("invoice", "Invoice")], default="freight"
    )

    purchase_import_tax = fields.Boolean(
        string="Create Invoice Tax?",
        default=False,
    )

    purchase_import_type = fields.Selection(
        selection=[
            ("amount_untaxed_signed", "Amount Untaxed"),
            ("amount_total_signed", "Amount Total"),
        ],
        string="Invoice Value",
        required=True,
        default="amount_untaxed_signed",
        help="The value of invoices in imports.",
    )
