# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    activate_filter_sale = fields.Boolean(
        string='Activate Filter Sale', default=False)
    activate_filter_purchase = fields.Boolean(
        string='Activate Filter Purchase', default=False)
    block_contact_without_account_position = fields.Boolean(
        'Block by contact without account position',
        help='Validate if the contact has not been assigned '
        'an account position and block the current sale order.'
    )
