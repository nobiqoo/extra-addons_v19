# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    insurable_value_percentage = fields.Float(
        related='company_id.insurable_value_percentage',
        readonly=False,
    )
