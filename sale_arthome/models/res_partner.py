# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_carrier = fields.Boolean(
        string="Is Carrier",
        help="Mark this contact as a carrier so it can be selected as the carrier of sales orders and deliveries.",
    )
