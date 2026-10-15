# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    purchase_method = fields.Selection(
        selection=[
            ('purchase', 'On ordered quantities'),
            ('receive', 'On received quantities'),
        ],
        string='Control Policy',
        copy=False,
        help='On ordered quantities: Control bills based on ordered quantities. \n On received quantities: Control bills based on received quantities.'
    )
