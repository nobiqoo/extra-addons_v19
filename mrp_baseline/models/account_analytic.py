# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    mrp_workorder_id = fields.Many2one(
        comodel_name='mrp.workorder',
        copy=False
    )
