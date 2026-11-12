
from odoo import api, fields, models

ANALYTIC_ACCOUNT_TYPES = [
    ('income', 'Income'),
    ('expense', 'Expense'),
    ('cost_sale', 'Cost of Sale'),
    ('cost_operation', 'Cost of Operation'),
]


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    account_type = fields.Selection(
        selection=ANALYTIC_ACCOUNT_TYPES,
        string='Type',
    )

    def _get_accountant_account_type(self):
        """Tipo de la cuenta analítica; si no tiene, el del plan más cercano hasta el raíz."""
        self.ensure_one()
        return self.account_type or self.plan_id._get_accountant_account_type()

    @api.model
    def _get_accountant_identifier_from_distribution(self, distribution):
        """Primera cuenta analítica de la distribución cuyo plan raíz tiene 'Identificación Cuenta Contable'
        y que resuelve un tipo (propio o heredado); las que no tienen tipo en ningún nivel no bloquean a las demás."""
        analytic_ids = []
        for key in (distribution or {}).keys():
            for part in str(key).split(","):
                part = part.strip()
                if part.isdigit():
                    analytic_ids.append(int(part))
        for analytic_account in self.browse(analytic_ids).exists():
            if (
                analytic_account.root_plan_id.account_accountant_identifier
                and analytic_account._get_accountant_account_type()
            ):
                return analytic_account
        return self.browse()

    @api.model
    def _get_accountant_target_account(self, product, distribution):
        """Cuenta contable que corresponde al tipo de la analítica identificadora,
        tomada del producto o de su categoría. Vacío si no aplica la regla."""
        target_account = self.env['account.account']
        analytic_account = self._get_accountant_identifier_from_distribution(distribution)
        if not analytic_account or not product:
            return target_account
        account_type = analytic_account._get_accountant_account_type()
        if not account_type:
            return target_account

        target_account = {
            "income": product.property_account_income_id,
            "expense": product.property_account_expense_id,
            "cost_sale": product.property_account_cost_sale_id,
            "cost_operation": product.property_account_cost_operation_id,
        }.get(account_type) or target_account

        if not target_account and product.categ_id:
            target_account = {
                "income": product.categ_id.property_account_income_categ_id,
                "expense": product.categ_id.property_account_expense_categ_id,
                "cost_sale": product.categ_id.property_account_cost_sale_categ_id,
                "cost_operation": product.categ_id.property_account_cost_operation_categ_id,
            }.get(account_type) or target_account
        return target_account
