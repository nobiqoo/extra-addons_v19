# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    purchase_lot_analytic_control = fields.Boolean(
        string='Lot Control by Analytic Account on Purchases',
        default=False,
    )
    purchase_lot_analytic_plan_id = fields.Many2one(
        'account.analytic.plan',
        string='Analytic Plan for Lots',
        domain="[('parent_id', '=', False)]",
    )
