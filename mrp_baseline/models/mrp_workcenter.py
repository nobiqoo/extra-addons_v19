# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    costs_hour_account_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Accounting Account'
    )
