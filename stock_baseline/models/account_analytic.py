# -*- coding: utf-8 -*-

from odoo import api, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('default_group_id'):
            self = self.with_context(default_group_id=False)
        return super().create(vals_list)
