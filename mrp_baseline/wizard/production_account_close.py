# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import ValidationError


ACCOUNT_DOMAIN = [('deprecated', '=', False), ('account_type', 'not in', ('asset_receivable',
                                                                          'liability_payable', 'asset_cash', 'liability_credit_card', 'off_balance'))]


class ProductionAccountClose(models.TransientModel):
    _name = 'production.account.close'
    _description = 'Close Production Accounts'

    accounts_ids = fields.Many2many(
        comodel_name='account.account',
        domain=ACCOUNT_DOMAIN
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company
    )

    costs_ids = fields.Many2many(
        comodel_name='stock.landed.cost'
    )

    date_start = fields.Date()
    date_end = fields.Date()

    line_ids = fields.One2many(
        comodel_name='production.account.close.line',
        inverse_name='close_id'
    )

    def query_get(self):
        return """
            select
                account_id as account_id,
                -- product_id as product_id,
                sum(debit) as debit,
                sum(credit) as credit
            from
                account_move_line
            where
                parent_state = 'posted'
                and company_id = %s
                and account_id = %s
                and date between '%s' and '%s'
                -- and product_id is not null
            group by
                account_id
            -- having
            --     sum(debit) - sum(credit) =! 0;
        """

    def query_get_account(self, account):
        query_get = self.query_get()
        query = query_get % (
            self.env.company.id,
            account.id,
            fields.Date.to_string(self.date_start),
            fields.Date.to_string(self.date_end)
        )
        self._cr.execute(query)
        return self._cr.dictfetchall()

    def action_return(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Close Production Accounts'),
            'res_model': 'production.account.close',
            # 'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }

    def action_calculate(self):
        self.line_ids.unlink()

        line_ids = []
        for account in self.accounts_ids:
            products = self.query_get_account(account)
            for product in products:
                debit = product.get('debit')
                credit = product.get('credit')
                residual = debit - credit
                vals = {
                    'account_id': account.id,
                    # 'product_id': product.get('product_id'),
                    'debit': debit,
                    'credit': credit,
                    'residual': residual
                }
                line_ids.append((0, 0, vals))

        self.write({'line_ids': line_ids})

        return self.action_return()

    def action_confirm(self):
        Cost = self.env['stock.landed.cost']
        Production = self.env['mrp.production']

        for line in self.line_ids:
            if not line.residual:
                continue

            production_domain = [
                ('state', '=', 'done'),
                ('cost_id.date', '>=', self.date_start),
                ('cost_id.date', '<=', self.date_end),
                ('cost_ids.account_id', '=', line.account_id.id)
            ]
            productions = Production.search(production_domain)
            if not productions:
                # TODO
                # Error message
                continue

            cost_vals = {
                'account_journal_id': self.env.ref('mrp_baseline.journal_mrp_cost').id,
                'date': fields.Date.today(),
                'target_model': 'manufacturing',
                'mrp_production_ids': [(6, 0, productions.ids)],
                'cost_lines': [(0, 0, {
                    'account_id': line.account_id.id,
                    'name': line.account_id.name,
                    'price_unit': line.residual,
                    'product_id': self.env.ref('mrp_baseline.product_mrp_close').id,
                    'split_method': 'equal'
                })]
            }
            cost = Cost.create(cost_vals)
            cost.button_validate()
            self.write({'costs_ids': [(4, cost.id, 0)]})

        return self.action_calculate()


class ProductionAccountCloseLine(models.TransientModel):
    _name = 'production.account.close.line'
    _description = 'Close Production Accounts Lines'

    account_id = fields.Many2one('account.account')

    close_id = fields.Many2one('production.account.close')

    credit = fields.Monetary()

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.company.currency_id
    )

    debit = fields.Monetary()

    residual = fields.Monetary()
