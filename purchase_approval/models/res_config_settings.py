# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    pr_approval_po = fields.Boolean(
        related='company_id.pr_approval_po',
        string="Flujo de aprobación orden de compra",
        readonly=False)
    