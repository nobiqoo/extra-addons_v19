
from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _is_stock_valuated_purchase_line(self):
        """En v19 la línea de compra de un bien con valoración automática va a la cuenta
        de inventario; el costo se reconoce al vender (línea cogs), así que no se reemplaza."""
        self.ensure_one()
        product = self.product_id
        return (
            'valuation' in product._fields
            and product.is_storable
            and product.with_company(self.company_id).valuation == 'real_time'
        )

    @api.onchange('analytic_distribution')
    def _onchange_analytic_distribution(self):
        if (
            self.analytic_distribution
            and self.move_type in ('in_invoice', 'in_refund')
            and not self._is_stock_valuated_purchase_line()
        ):
            target_account = self.env['account.analytic.account']._get_accountant_target_account(
                self.product_id, self.analytic_distribution)
            if target_account:
                self.account_id = target_account

    @api.model_create_multi
    def create(self, vals_list):
        self._prepare_cogs_analytic_account_mapping(vals_list)
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

    @api.model
    def _prepare_cogs_analytic_account_mapping(self, vals_list):
        """Costo de venta (anglosajón): solo se reemplaza la cuenta del débito al costo.
        En 19 ambas líneas 'cogs' traen analytic_distribution, así que la línea de
        inventario se distingue por la cuenta de valoración del producto y no se modifica."""
        for vals in vals_list:
            if (
                vals.get('display_type') != 'cogs'
                or not vals.get('analytic_distribution')
                or not vals.get('product_id')
                or not vals.get('move_id')
            ):
                continue
            move = self.env['account.move'].browse(vals['move_id'])
            product = self.env['product.product'].with_company(move.company_id).browse(vals['product_id'])
            accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=move.fiscal_position_id)
            stock_account = accounts.get('stock_valuation')
            if stock_account and vals.get('account_id') == stock_account.id:
                continue
            target_account = self.env['account.analytic.account']._get_accountant_target_account(
                product, vals['analytic_distribution'])
            if target_account:
                vals['account_id'] = target_account.id

    def _apply_purchase_analytic_account_mapping(self):
        for line in self:
            move = line.move_id
            if (
                not move
                or not move.is_purchase_document(include_receipts=False)
                or not line.analytic_distribution
                or line._is_stock_valuated_purchase_line()
            ):
                continue

            target_account = self.env["account.analytic.account"]._get_accountant_target_account(
                line.product_id.with_company(move.company_id), line.analytic_distribution)
            if target_account and line.account_id != target_account:
                line.with_context(skip_purchase_analytic_account=True).write(
                    {"account_id": target_account.id}
                )
