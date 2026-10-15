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

            # Obtener IDs de cuentas analíticas
            analytic_ids = []
            for key in expense.analytic_distribution.keys():
                for part in str(key).split(","):
                    if part.strip().isdigit():
                        analytic_ids.append(int(part))

            if not analytic_ids:
                continue

            analytic_accounts = self.env["account.analytic.account"].browse(
                analytic_ids)

            analytic_account_identifier = False
            for analytic_account in analytic_accounts:
                if analytic_account.plan_id.account_accountant_identifier:
                    analytic_account_identifier = analytic_account
                    break

            if not analytic_account_identifier:
                continue

            account_type = analytic_account_identifier.account_type
            if not account_type:
                continue

            product = expense.product_id

            target_account = {
                "income": product.property_account_income_id,
                "expense": product.property_account_expense_id,
                "cost_sale": getattr(product, "property_account_cost_sale_id", False),
                "cost_operation": getattr(product, "property_account_cost_operation_id", False),
            }.get(account_type)

            if not target_account and product.categ_id:
                target_account = {
                    "income": product.categ_id.property_account_income_categ_id,
                    "expense": product.categ_id.property_account_expense_categ_id,
                    "cost_sale": getattr(product.categ_id, "property_account_cost_sale_categ_id", False),
                    "cost_operation": getattr(product.categ_id, "property_account_cost_operation_categ_id", False),
                }.get(account_type)

            if target_account and expense.account_id != target_account:
                expense.account_id = target_account
