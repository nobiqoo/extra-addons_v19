# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    conditioned_rate_type = fields.Selection(
        selection=[
            ('fixed', 'Fixed Amount'),
            ('percentage', 'Percentage'),
        ],
        string='Conditioned Exchange Rate Type',
        help=(
            "If set, the standard exchange rate (TRM) used to convert this partner's "
            "sale and purchase invoice lines to another currency is adjusted before "
            "being applied: either by adding a fixed amount to it, or by increasing it "
            "by a percentage. The same adjustment is used regardless of the currency "
            "being converted."
        ),
    )
    conditioned_rate_value = fields.Float(
        string='Conditioned Exchange Rate Value',
        help=(
            "Fixed amount or percentage added on top of the standard exchange rate "
            "(TRM), depending on the selected Conditioned Exchange Rate Type."
        ),
    )
