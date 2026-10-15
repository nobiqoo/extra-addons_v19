# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    negative_inventory = fields.Boolean(
        related='company_id.negative_inventory',
        readonly=False
    )
