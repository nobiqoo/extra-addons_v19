# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class hr_expense(models.Model):
    _inherit = "hr.expense"

    @api.onchange('analytic_distribution', 'product_id')
    def _onchange_analytic_distribution_account(self):
        """Cambia la cuenta contable según la distribución analítica"""
        for expense in self:
            if not expense.analytic_distribution or not expense.product_id:
                self._compute_account_id()
                continue

            target_account = self.env["account.analytic.account"]._get_accountant_target_account(
                expense.product_id, expense.analytic_distribution)

            if target_account and expense.account_id != target_account:
                expense.account_id = target_account
