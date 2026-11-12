# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    invoice_manually_from_picking = fields.Boolean(
        string='Invoice manually from delivery',
        default=False,
        help='If checked, delivery orders for this contact will not '
             'generate an automatic invoice; they must be invoiced manually.',
    )
