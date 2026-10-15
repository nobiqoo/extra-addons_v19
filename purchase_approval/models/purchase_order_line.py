
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    budget_line_id = fields.Many2one(
        comodel_name='crossovered.budget.lines',
        string='Línea de presupuesto'
    )
    amount_to_budget = fields.Float(
        string='Monto aplicado en presupuesto'
    )

    def get_budget_data(self):
        for record in self:
            record._get_budget_data()

    def _get_budget_data(self):
        for record in self:
            if self.env.company.purchase_budget_controll:
                product = record.product_id
                if isinstance(record.analytic_distribution, dict):
                    for id_analytic, value in record.analytic_distribution.items():
                        analytic = self.env['account.analytic.account'].browse(int(id_analytic))
                        account = record._get_account_budget(product, analytic)
                        if account.code[0] not in ['1', '2', '3']:
                            budget_line = record._get_budget_line(product, account, analytic, date=record.date_order)
                            record.budget_line_id = budget_line
                            record.amount_to_budget = (record.price_subtotal * (value / 100)) * -1

    def _get_account_budget(self, product, analytic):
        account = False
        if analytic.account_type == 'income':
            if product.property_account_income_id:
                account = product.property_account_income_id
            else:
                account = product.categ_id.property_account_income_categ_id
        elif analytic.account_type == 'expense':
            if product.property_account_expense_id:
                account = product.property_account_expense_id
            else:
                account = product.categ_id.property_account_expense_categ_id
        elif analytic.account_type == 'cost_sale':
            if product.property_account_cost_sale_id:
                account = product.property_account_cost_sale_id
            else:
                account = product.categ_id.property_account_cost_sale_categ_id
        elif analytic.account_type == 'cost_operation':
            if product.property_account_cost_operation_id:
                account = product.property_account_cost_operation_id
            else:
                account = product.categ_id.property_account_cost_operation_categ_id
        if not account:
            raise ValidationError('No se ha configurado una cuenta para el '
                                  'tipo de analitica en las cuentas del producto o categoría')
        return account

    @api.model
    def _get_budget_line(self, product, account, analytic, date):
        date_order = date.date()
        general_budgets = self.env['account.budget.post'].search([
            ('account_ids', 'in', [account.id])
        ])
        budget_lines = self.env['crossovered.budget.lines'].search([
            ('general_budget_id', 'in', general_budgets.ids),
            ('analytic_account_id', '=', analytic.id),
            ('date_from', '<=', date_order),
            ('date_to', '>=', date_order),
            ('crossovered_budget_id.state', '=', 'validate'),
            ('planned_amount', '<', 0)
        ], limit=1)
        if not budget_lines:
            raise ValidationError('No se ha encontrado línea de '
                                  'presupuesto que coincida con la línea de la '
                                  'orden de compra:\nProducto: {product}\nCuenta: {account}\nAnalítica: {analytic}'.format(
                                      product=product.display_name,
                                      account=account.display_name,
                                      analytic=analytic.display_name
                                  ))
        return budget_lines

    def check_available_budget(self):
        total_amount = self.amount_to_budget + self.budget_line_id.commited_amount
        if total_amount < self.budget_line_id.planned_amount:
            return False
        return True
