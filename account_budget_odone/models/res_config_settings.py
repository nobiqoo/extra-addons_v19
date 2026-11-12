# -*- coding: utf-8 -*-

from odoo import fields, models, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    purchase_budget_controll = fields.Boolean(
        related='company_id.purchase_budget_controll',
        readonly=False,
    )