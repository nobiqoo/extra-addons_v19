
from odoo import api, models, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('analytic_distribution')
    def _onchange_analytic_distribution(self):
        if self.analytic_distribution:
            distribution = self.analytic_distribution
            if len(distribution) and self.move_type in ('in_invoice', 'in_refund'):
                analytic_ids = []
                for key in distribution.keys():
                    for part in str(key).split(","):
                        part = part.strip()
                        if part.isdigit():
                            analytic_ids.append(int(part))
                analytic_accounts = self.env['account.analytic.account'].browse(analytic_ids)
                analytic_account_identifier = False
                for analytic_account in analytic_accounts:
                    if analytic_account.plan_id.account_accountant_identifier:
                        analytic_account_identifier = analytic_account
                        break
                if not analytic_account_identifier:
                    return
                account_type = analytic_account_identifier.account_type
                account_mapping = {
                    'income': self.product_id.property_account_income_id,
                    'expense': self.product_id.property_account_expense_id,
                    'cost_sale': self.product_id.property_account_cost_sale_id,
                    'cost_operation': self.product_id.property_account_cost_operation_id,
                }
                account_mapping_categ = {
                    'income': self.product_id.categ_id.property_account_income_categ_id,
                    'expense': self.product_id.categ_id.property_account_expense_categ_id,
                    'cost_sale': self.product_id.categ_id.property_account_cost_sale_categ_id,
                    'cost_operation': self.product_id.categ_id.property_account_cost_operation_categ_id,
                }
                self.account_id = account_mapping.get(account_type)
                if not self.account_id:
                    self.account_id = account_mapping_categ.get(account_type)
                    # if not self.account_id:
                    #     raise UserError(_('Invalid account type: %s, please configure account in accountant/product') % account_type)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._apply_purchase_analytic_account_mapping()

        return lines

    def write(self, vals):
        if self.env.context.get("skip_purchase_analytic_account"):
            return super().write(vals)
        res = super().write(vals)
        if any(field in vals for field in ("analytic_distribution", "product_id", "account_id")):
            self._apply_purchase_analytic_account_mapping()
        return res

    def _apply_purchase_analytic_account_mapping(self):
        for line in self:
            move = line.move_id
            if (
                not move
                or not move.is_purchase_document(include_receipts=False)
                or not line.analytic_distribution
            ):
                continue

            analytic_ids = []
            for key in line.analytic_distribution.keys():
                for part in str(key).split(","):
                    part = part.strip()
                    if part.isdigit():
                        analytic_ids.append(int(part))

            analytic_accounts = self.env["account.analytic.account"].browse(analytic_ids)
            analytic_account_identifier = False
            for analytic_account in analytic_accounts:
                if analytic_account.plan_id.account_accountant_identifier:
                    analytic_account_identifier = analytic_account
                    break
            if not analytic_account_identifier:
                return
            account_type = analytic_account_identifier.account_type
            target_account = False
            product = line.product_id
            if product:
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

            if target_account and line.account_id != target_account:
                line.with_context(skip_purchase_analytic_account=True).write(
                    {"account_id": target_account.id}
                )