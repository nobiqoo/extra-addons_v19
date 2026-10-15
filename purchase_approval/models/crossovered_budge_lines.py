
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

from collections import defaultdict


class CrossoveredBudgetLines(models.Model):
    _inherit = 'crossovered.budget.lines'

    order_line_ids = fields.One2many(
        comodel_name='purchase.order.line',
        string='Líneas ordenes de compra',
        inverse_name='budget_line_id'
    )
    commited_amount = fields.Monetary(
        compute='_compute_commited_amount',
        string='Importe comprometido'
    )

    def _compute_commited_amount(self):
        def get_accounts(line):
            if line.analytic_account_id:
                return 'account.analytic.line', set(line.analytic_account_id.ids)
            return 'account.move.line', set(line.general_budget_id.account_ids.ids)

        def get_query(model, date_from, date_to, account_ids):
            domain = [
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('account_id', 'in', list(account_ids)),
            ]
            if model == 'account.move.line':
                fname = '-balance'
                general_account = 'account_id'
                domain += [('parent_state', '=', 'posted')]
            else:
                fname = 'amount'
                general_account = 'general_account_id'

            query = self.env[model]._search(domain)
            query.order = None
            query_str, params = query.select('%s', '%s', '%s', 'account_id', general_account, f'SUM({fname})')
            params = [model, date_from, date_to] + params
            query_str += f" GROUP BY account_id, {general_account}"

            return query_str, params

        groups = defaultdict(lambda: defaultdict(set))
        for line in self:
            model, accounts = get_accounts(line)
            groups[model][(line.date_from, line.date_to)].update(accounts)

        queries = []
        queries_params = []
        for model, by_date in groups.items():
            for (date_from, date_to), account_ids in by_date.items():
                if account_ids:
                    query, params = get_query(model, date_from, date_to, account_ids)
                    queries.append(query)
                    queries_params += params

        if not queries:
            self.commited_amount = 0
            return

        self.env.cr.execute(" UNION ALL ".join(queries), queries_params)

        agg_general = defaultdict(lambda: defaultdict(float)) 
        agg_analytic = defaultdict(lambda: defaultdict(float))
        for model, date_from, date_to, account_id, general_account_id, amount in self.env.cr.fetchall():
            agg_general[(model, date_from, date_to)][(account_id, general_account_id)] += amount
            agg_analytic[(model, date_from, date_to)][account_id] += amount

        for line in self:
            invoices = []
            model, accounts = get_accounts(line)
            general_accounts = line.general_budget_id.account_ids
            line.commited_amount += sum(
                [x.amount_to_budget for x in line.order_line_ids.filtered(lambda x: x.state in ['purchase'])])
            for order_line in line.order_line_ids.filtered(lambda x: x.state in ['purchase']):
                invoices += order_line.order_id.invoice_ids.ids
            moves = self.env['account.move.line'].search([
                ('move_id', 'in', invoices),
                ('parent_state', '=', 'posted'),
                ('account_id', 'in', line.general_budget_id.account_ids.ids)])
            line.commited_amount += sum(moves.mapped('balance'))
            if general_accounts:
                line.commited_amount += sum(
                    agg_general.get((model, line.date_from, line.date_to), {}).get((account, general_account), 0)
                    for account in accounts
                    for general_account in general_accounts.ids
                )
            else:
                line.commited_amount += sum(
                    agg_analytic.get((model, line.date_from, line.date_to), {}).get(account, 0)
                    for account in accounts
                )

    def action_open_purchase_order_lines(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Líneas orden de compra',
            'res_model': 'purchase.order.line',
            'view_mode': 'list',
            'domain': [('id', 'in', self.order_line_ids.filtered(lambda x: x.state in ['purchase']).ids)],
            'target': 'current'
        }
