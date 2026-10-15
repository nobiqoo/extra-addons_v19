# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    activate_filter_sale = fields.Boolean(
        string='Activate Filter Sale',
        related='company_id.activate_filter_sale',
        readonly=False)
    activate_filter_purchase = fields.Boolean(
        string='Activate Filter Purchase',
        related='company_id.activate_filter_purchase',
        readonly=False)
    block_contact_without_account_position = fields.Boolean(
        related='company_id.block_contact_without_account_position',
        readonly=False
    )
