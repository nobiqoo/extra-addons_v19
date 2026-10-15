# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_mrp_cost = fields.Boolean(
        string='Manage BoM Costs',
        implied_group='mrp_baseline.group_mrp_cost'
    )
