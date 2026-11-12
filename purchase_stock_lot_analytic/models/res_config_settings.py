# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    purchase_lot_analytic_control = fields.Boolean(
        related='company_id.purchase_lot_analytic_control',
        string='Lot Control by Analytic Account on Purchases',
        readonly=False,
    )
    purchase_lot_analytic_plan_id = fields.Many2one(
        related='company_id.purchase_lot_analytic_plan_id',
        readonly=False,
    )
