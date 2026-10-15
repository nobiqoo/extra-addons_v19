# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

from ast import literal_eval
from collections import defaultdict
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL


class AccountReport(models.Model):
    _inherit = 'account.report'

    filter_seller = fields.Boolean('Sellers',
                                   default=False)
    filter_sale_team = fields.Boolean('Sales teams',
                                      default=False)

    # OPTIONS: Sellers
    def _init_options_seller(self, options, previous_options=None):
        if not self.filter_seller and not self.filter_sale_team:
            return
        options['seller'] = True
        if self.filter_seller:
            previous_seller_ids = previous_options and previous_options.get(
                'seller_ids') or []

            selected_seller_ids = [int(seller)
                                   for seller in previous_seller_ids]
            # search instead of browse so that record rules apply and filter out the ones the user does not have access to
            selected_sellers = selected_seller_ids and self.env['res.users'].search(
                [('id', 'in', selected_seller_ids)]) or self.env['res.users']
            options['selected_seller_ids'] = selected_sellers.mapped('name')
            options['seller_ids'] = selected_sellers.ids
        if self.filter_sale_team:
            # options['seller'] = True
            previous_team_ids = previous_options and previous_options.get('team_ids') or [
            ]

            selected_team_ids = [int(team) for team in previous_team_ids]
            # search instead of browse so that record rules apply and filter out the ones the user does not have access to
            selected_teams = selected_team_ids and self.env['crm.team'].search(
                [('id', 'in', selected_team_ids)]) or self.env['crm.team']
            options['selected_team_ids'] = selected_teams.mapped('name')
            options['team_ids'] = selected_teams.ids

    @api.model
    def _get_options_seller_domain(self, options):
        domain = []
        if options.get('seller_ids'):
            seller_ids = [int(seller) for seller in options['seller_ids']]
            domain.append(('move_id.invoice_user_id', 'in', seller_ids))
        if options.get('team_ids'):
            team_ids = [int(team) for team in options['team_ids']]
            domain.append(('move_id.team_id', 'in', team_ids))
        return domain

    # Base
    def _get_options_domain(self, options, date_scope):
        domain = super()._get_options_domain(options, date_scope)
        domain = domain & Domain(self._get_options_seller_domain(options))
        return domain

    # Override enterprise method to show niif balance in reports
    def _compute_formula_batch_with_engine_domain(self, options, date_scope, formulas_dict, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        """ Report engine.

        Formulas made for this engine consist of a domain on account.move.line. Only those move lines will be used to compute the result.

        This engine supports a few subformulas, each returning a slighlty different result:
        - sum: the result will be sum of the matched move lines' balances

        - sum_if_pos: the result will be the same as sum only if it's positive; else, it will be 0

        - sum_if_neg: the result will be the same as sum only if it's negative; else, it will be 0

        - count_rows: the result will be the number of sublines this expression has. If the parent report line has no groupby,
                      then it will be the number of matching amls. If there is a groupby, it will be the number of distinct grouping
                      keys at the first level of this groupby (so, if groupby is 'partner_id, account_id', the number of partners).
        """
        def _format_result_depending_on_groupby(formula_rslt):
            if not current_groupby:
                if formula_rslt:
                    # There should be only one element in the list; we only return its totals (a dict) ; so that a list is only returned in case
                    # of a groupby being unfolded.
                    return formula_rslt[0][1]
                else:
                    # No result at all
                    return {
                        'sum': 0,
                        'sum_if_pos': 0,
                        'sum_if_neg': 0,
                        'count_rows': 0,
                        'has_sublines': False,
                    }
            return formula_rslt

        self._check_groupby_fields((next_groupby.split(',') if next_groupby else [
        ]) + ([current_groupby] if current_groupby else []))

        groupby_sql = SQL.identifier(
            'account_move_line', current_groupby) if current_groupby else None

        rslt = {}

        for formula, expressions in formulas_dict.items():
            try:
                line_domain = literal_eval(formula)
            except (ValueError, SyntaxError):
                raise UserError(_(
                    'Invalid domain formula in expression "%(expression)s" of line "%(line)s": %(formula)s',
                    expression=expressions.label,
                    line=expressions.report_line_id.name,
                    formula=formula,
                ))
            query = self._get_report_query(
                options, date_scope, domain=line_domain)

            tail_query = self._get_engine_query_tail(offset, limit)
            query = SQL(
                """
                SELECT
                    COALESCE(SUM(%(balance_select)s), 0.0) AS sum,
                    COALESCE(SUM(%(balance_select_ifrs)s), 0.0) AS sum_ifrs,
                    COUNT(DISTINCT account_move_line.%(select_count_field)s) AS count_rows
                    %(select_groupby_sql)s
                FROM %(table_references)s
                %(currency_table_join)s
                WHERE %(search_condition)s
                %(group_by_groupby_sql)s
                %(order_by_sql)s
                %(tail_query)s
                """,
                select_count_field=SQL.identifier(
                    next_groupby.split(',')[0] if next_groupby else 'id'),
                select_groupby_sql=SQL(
                    ', %s AS grouping_key', groupby_sql) if groupby_sql else SQL(),
                table_references=query.from_clause,
                balance_select=self._currency_table_apply_rate(
                    SQL("account_move_line.balance")),
                balance_select_ifrs=self._currency_table_apply_rate(
                    SQL("account_move_line.ifrs_balance")),
                currency_table_join=self._currency_table_aml_join(options),
                search_condition=query.where_clause,
                group_by_groupby_sql=SQL(
                    'GROUP BY %s', groupby_sql) if groupby_sql else SQL(),
                order_by_sql=SQL(
                    ' ORDER BY %s', groupby_sql) if groupby_sql else SQL(),
                tail_query=tail_query,
            )

            # Fetch the results.
            formula_rslt = []
            self._cr.execute(query)
            all_query_res = self._cr.dictfetchall()

            total_sum = 0
            total_sum_ifrs_balance = 0
            for query_res in all_query_res:
                res_sum_ifrs_balance = query_res['sum_ifrs']
                res_sum = query_res['sum']
                total_sum_ifrs_balance += res_sum_ifrs_balance
                total_sum += res_sum
                totals = {
                    'sum': res_sum,
                    'sum_ifrs_balance': res_sum_ifrs_balance,
                    'sum_if_pos': 0,
                    'sum_if_neg': 0,
                    'count_rows': query_res['count_rows'],
                    'has_sublines': query_res['count_rows'] > 0,
                }
                formula_rslt.append(
                    (query_res.get('grouping_key', None), totals))

            # Handle sum_if_pos, -sum_if_pos, sum_if_neg and -sum_if_neg
            expressions_by_sign_policy = defaultdict(
                lambda: self.env['account.report.expression'])
            for expression in expressions:
                subformula_without_sign = expression.subformula.replace(
                    '-', '').strip()
                if subformula_without_sign in ('sum_if_pos', 'sum_if_neg'):
                    expressions_by_sign_policy[subformula_without_sign] += expression
                else:
                    expressions_by_sign_policy['no_sign_check'] += expression

            # Then we have to check the total of the line and only give results if its sign matches the desired policy.
            # This is important for groupby managements, for which we can't just check the sign query_res by query_res
            if expressions_by_sign_policy['sum_if_pos'] or expressions_by_sign_policy['sum_if_neg']:
                sign_policy_with_value = 'sum_if_pos' if self.env.company.currency_id.compare_amounts(
                    total_sum, 0.0) >= 0 else 'sum_if_neg'
                # >= instead of > is intended; usability decision: 0 is considered positive

                formula_rslt_with_sign = [(grouping_key, {
                                           **totals, sign_policy_with_value: totals['sum']}) for grouping_key, totals in formula_rslt]

                for sign_policy in ('sum_if_pos', 'sum_if_neg'):
                    policy_expressions = expressions_by_sign_policy[sign_policy]

                    if policy_expressions:
                        if sign_policy == sign_policy_with_value:
                            rslt[(formula, policy_expressions)] = _format_result_depending_on_groupby(
                                formula_rslt_with_sign)
                        else:
                            rslt[(formula, policy_expressions)
                                 ] = _format_result_depending_on_groupby([])

            if expressions_by_sign_policy['no_sign_check']:
                rslt[(formula, expressions_by_sign_policy['no_sign_check'])
                     ] = _format_result_depending_on_groupby(formula_rslt)

        return rslt
