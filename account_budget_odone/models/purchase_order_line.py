from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    

    crossovered_budget_line_id = fields.Many2one(
        comodel_name='crossovered.budget.lines',
        string='Línea de presupuesto'
    )
    
    amount_to_budget = fields.Float(
        string='Monto aplicado en presupuesto'
    )
    

    def _get_budget_data(self):
        for record in self:
            
            product = record.product_id
            if isinstance(record.analytic_distribution, dict):
                 for analytic_ids, value in record.analytic_distribution.items():
                    for analytic_id in analytic_ids.split(','):
                        analytic = self.env['account.analytic.account'].browse(int(analytic_id))
                        accounts = record._get_account_budget(product, analytic)
                        valid_accounts = accounts.filtered(
                            lambda a: a.code and a.code[0] not in ('1', '2', '3')
                        )
                        if not valid_accounts:
                            # Product only has balance sheet accounts
                            # (Assets/Liabilities/Equity, codes 1-3), no
                            # P&L account to budget against, so budget
                            # tracking doesn't apply to this line.
                            continue
                        budget_line = record._get_budget_line(product, valid_accounts, analytic, date=record.date_order)
                        record.crossovered_budget_line_id = budget_line
                        amount = record.price_subtotal * (value / 100)
                        record.amount_to_budget = -abs(amount)

    def _get_account_budget(self, product, analytic):
        accounts = self.env['account.account']
        # account_analytic.account_type ('income'/'expense'/'cost_sale'/
        # 'cost_operation') is what actually decides which account gets
        # posted to the ledger (see account_analytic's
        # _apply_purchase_analytic_account_mapping/_onchange_analytic_distribution).
        # Some products/categories (e.g. EVENTOS COMERCIALES) are only ever
        # configured with a Cost of Sale/Operation account, never an
        # Income/Expense one, so budgeting must look at the same account
        # the analytic type points to instead of always requiring Income/Expense.
        account_type_fields = {
            'income': ('property_account_income_id', 'property_account_income_categ_id'),
            'expense': ('property_account_expense_id', 'property_account_expense_categ_id'),
            'cost_sale': ('property_account_cost_sale_id', 'property_account_cost_sale_categ_id'),
            'cost_operation': ('property_account_cost_operation_id', 'property_account_cost_operation_categ_id'),
        }
        product_field, categ_field = account_type_fields.get(
            analytic.account_type, (None, None)
        )
        if product_field:
            accounts |= (
                getattr(product, product_field, False)
                or getattr(product.categ_id, categ_field, False)
            )

        if not accounts:
            # The account matching the analytic's own type isn't configured
            # (or the analytic has no type set): fall back to whichever of
            # the four account types IS configured on the product/category,
            # instead of only ever checking Income/Expense.
            for fallback_product_field, fallback_categ_field in account_type_fields.values():
                accounts |= (
                    getattr(product, fallback_product_field, False)
                    or getattr(product.categ_id, fallback_categ_field, False)
                )
        if not accounts:
            raise ValidationError('No se ha configurado una cuenta para el '
                                  'producto o en su categoría')
        return accounts
    
    @api.model
    def _get_budget_line(self, product, accounts, analytic, date):
        date_order = date.date()
        general_budgets = self.env['account.budget.post'].search([
            ('account_ids', 'in', accounts.ids)
        ])
        budget_lines = self.env['crossovered.budget.lines'].search([
            ('general_budget_id', 'in', general_budgets.ids),
            ('analytic_account_id', '=', analytic.id),
            ('date_from', '<=', date_order),
            ('date_to', '>=', date_order),
            ('crossovered_budget_id.state', '=', 'validate')
        ], limit=1)
        if not budget_lines:
            raise ValidationError('No se ha encontrado línea de '
                                  'presupuesto que coincida con la línea de la '
                                  'orden de compra:\nProducto: {product}\nCuenta: {account}\nAnalítica: {analytic}'.format(
                                      product=product.display_name,
                                      account=', '.join(accounts.mapped('display_name')),
                                      analytic=analytic.display_name
                                  ))
        return budget_lines

    def check_available_budget(self):
        total_amount = self.amount_to_budget + self.crossovered_budget_line_id.commited_amount
        if abs(total_amount) > abs(self.crossovered_budget_line_id.planned_amount):
            return False
        return True