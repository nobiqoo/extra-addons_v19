# -*- coding: utf-8 -*-

from itertools import chain

from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.tools import SQL

# Campos de la operación logística en account.move. Existen con el mismo
# nombre en account_cargowise_sync y en account_logistic_odone (y la TRM
# también en account_baseline); si ninguno está instalado la columna sale vacía.
OPTIONAL_MOVE_FIELDS = {
    'container_number': 'container_number',
    'move_position': 'position',
    'invoice_origin': 'origin',
    'invoice_destination': 'destination',
    'exchange_rate': 'current_exchange_rate',
}

# Columnas que solo tienen sentido a nivel de documento (apunte)
DOCUMENT_VALUES = (
    'move_number', 'move_currency', 'analytic_account', 'identification_type',
    'identification_number', 'invoice_ref', 'country_name', 'journal_name',
    'report_date', 'account', 'amount_invoice', 'amount_residual',
    'currency_id', *OPTIONAL_MOVE_FIELDS,
)


class AccountStatementReportHandler(models.AbstractModel):
    """Port del informe "Estados de cuentas" de Consolcargo v15
    (account.accounts.states de account_reports_consolcargo): cartera por
    edades de cuentas por cobrar y por pagar en un mismo informe, con el signo
    del saldo contable (las cuentas por pagar salen negativas)."""
    _name = 'account.statement.report.handler'
    _inherit = ['account.aged.partner.balance.report.handler']
    _description = 'Estados de Cuentas Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # Orden por defecto del estándar (invoice_date) no existe en este informe
        if options['order_column'].get('expression_label') not in {
                col['expression_label'] for col in options['columns']}:
            options['order_column'] = {'expression_label': 'report_date', 'direction': 'ASC'}

    def _report_custom_engine_account_statement(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        report._check_groupby_fields((next_groupby.split(',') if next_groupby else []) + ([current_groupby] if current_groupby else []))

        def minus_days(date_obj, days):
            return fields.Date.to_string(date_obj - relativedelta(days=days))

        aging_date_field = SQL.identifier('invoice_date') if options['aging_based_on'] == 'base_on_invoice_date' else SQL.identifier('date_maturity')
        date_to = fields.Date.from_string(options['date']['date_to'])
        interval = options['aging_interval']
        periods = [(False, fields.Date.to_string(date_to))]
        nb_periods = len([column for column in options['columns'] if column['expression_label'].startswith('period')]) - 1
        for i in range(nb_periods):
            start_date = minus_days(date_to, (interval * i) + 1)
            end_date = minus_days(date_to, interval * (i + 1)) if i < nb_periods - 1 else False
            periods.append((start_date, end_date))

        period_table = SQL(
            '(VALUES %s)' % ','.join("(%s, %s, %s)" for period in periods),
            *chain.from_iterable(
                (period[0] or None, period[1] or None, i)
                for i, period in enumerate(periods)
            ),
        )

        query = report._get_report_query(options, 'strict_range', domain=[
            ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
        ])
        account_alias = query.left_join(lhs_alias='account_move_line', lhs_column='account_id', rhs_table='account_account', rhs_column='id', link='account_id')
        account_code = self.env['account.account']._field_to_sql(account_alias, 'code', query)

        always_present_groupby = SQL("period_table.period_index")
        if current_groupby:
            groupby_field_sql = self.env['account.move.line']._field_to_sql("account_move_line", current_groupby, query)
            select_from_groupby = SQL("%s AS grouping_key,", groupby_field_sql)
            groupby_clause = SQL("%s, %s", groupby_field_sql, always_present_groupby)
        else:
            select_from_groupby = SQL()
            groupby_clause = always_present_groupby

        select_period_query = SQL(',').join(
            SQL(
                """
                CASE WHEN period_table.period_index = %(period_index)s
                THEN SUM(%(balance_select)s)
                ELSE 0 END AS %(column_name)s
                """,
                period_index=i,
                column_name=SQL.identifier(f"period{i}"),
                balance_select=report._currency_table_apply_rate(SQL(
                    "account_move_line.balance - COALESCE(part_debit.amount, 0) + COALESCE(part_credit.amount, 0)"
                )),
            )
            for i in range(len(periods))
        )

        move_fields = self.env['account.move']._fields
        select_optional = SQL(',').join(
            SQL(
                "ARRAY_AGG(DISTINCT move_st.%s) AS %s",
                SQL.identifier(field_name), SQL.identifier(label),
            ) if field_name in move_fields and move_fields[field_name].store
            else SQL("ARRAY[NULL] AS %s", SQL.identifier(label))
            for label, field_name in OPTIONAL_MOVE_FIELDS.items()
        )

        # Total factura / total adeudado en la moneda del documento, con el
        # signo de la línea (misma regla que v15).
        document_sign = SQL(
            """CASE WHEN (account_account_st.account_type = 'asset_receivable'
                          AND account_move_line.credit > account_move_line.debit)
                      OR (account_account_st.account_type = 'liability_payable'
                          AND account_move_line.credit > account_move_line.debit)
                THEN -1 ELSE 1 END""")

        tail_query = report._get_engine_query_tail(offset, limit)
        query = SQL(
            """
            WITH period_table(date_start, date_stop, period_index) AS (%(period_table)s)

            SELECT
                %(select_from_groupby)s
                ARRAY_AGG(DISTINCT account_move_line.partner_id) AS partner_id,
                ARRAY_AGG(DISTINCT COALESCE(account_move_line.date_maturity, account_move_line.date)) AS report_date,
                ARRAY_AGG(DISTINCT %(account_code)s) AS account,
                ARRAY_AGG(DISTINCT account_move_line.currency_id) AS currency_id,
                ARRAY_AGG(DISTINCT account_move_line.journal_id) AS journal_id,
                ARRAY_AGG(DISTINCT move_st.name) AS move_number,
                ARRAY_AGG(DISTINCT move_st.ref) AS invoice_ref,
                (ARRAY_AGG(account_move_line.analytic_distribution))[1] AS analytic_distribution,
                ARRAY_AGG(DISTINCT CASE WHEN move_st.move_type = 'entry'
                    THEN account_move_line.amount_currency
                    ELSE %(document_sign)s * move_st.amount_total END) AS amount_invoice,
                ARRAY_AGG(DISTINCT CASE WHEN move_st.move_type = 'entry'
                    THEN account_move_line.amount_residual_currency
                    ELSE %(document_sign)s * move_st.amount_residual END) AS amount_residual,
                COUNT(DISTINCT account_move_line.id) AS line_count,
                %(select_optional)s,
                %(select_period_query)s

            FROM %(table_references)s

            JOIN account_move move_st ON move_st.id = account_move_line.move_id
            JOIN account_account account_account_st ON account_account_st.id = account_move_line.account_id
            %(currency_table_join)s

            LEFT JOIN LATERAL (
                SELECT SUM(part.amount) AS amount, part.debit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(date_to)s AND part.debit_move_id = account_move_line.id
                GROUP BY part.debit_move_id
            ) part_debit ON TRUE

            LEFT JOIN LATERAL (
                SELECT SUM(part.amount) AS amount, part.credit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(date_to)s AND part.credit_move_id = account_move_line.id
                GROUP BY part.credit_move_id
            ) part_credit ON TRUE

            JOIN period_table ON
                (
                    period_table.date_start IS NULL
                    OR COALESCE(account_move_line.%(aging_date_field)s, account_move_line.date) <= DATE(period_table.date_start)
                )
                AND
                (
                    period_table.date_stop IS NULL
                    OR COALESCE(account_move_line.%(aging_date_field)s, account_move_line.date) >= DATE(period_table.date_stop)
                )

            WHERE %(search_condition)s

            GROUP BY %(groupby_clause)s

            HAVING
                ROUND(SUM(%(having_debit)s), %(currency_precision)s) != 0
                OR ROUND(SUM(%(having_credit)s), %(currency_precision)s) != 0

            ORDER BY %(groupby_clause)s

            %(tail_query)s
            """,
            period_table=period_table,
            select_from_groupby=select_from_groupby,
            account_code=account_code,
            document_sign=document_sign,
            select_optional=select_optional,
            select_period_query=select_period_query,
            table_references=query.from_clause,
            currency_table_join=report._currency_table_aml_join(options),
            date_to=date_to,
            aging_date_field=aging_date_field,
            search_condition=query.where_clause,
            groupby_clause=groupby_clause,
            having_debit=report._currency_table_apply_rate(SQL("CASE WHEN account_move_line.balance > 0 THEN account_move_line.balance ELSE 0 END - COALESCE(part_debit.amount, 0)")),
            having_credit=report._currency_table_apply_rate(SQL("CASE WHEN account_move_line.balance < 0 THEN -account_move_line.balance ELSE 0 END - COALESCE(part_credit.amount, 0)")),
            currency_precision=self.env.company.currency_id.decimal_places,
            tail_query=tail_query,
        )
        self.env.cr.execute(query)
        query_res_lines = self.env.cr.dictfetchall()

        records = self._statement_prefetch(query_res_lines) if current_groupby == 'id' else {}

        def build_result_dict(query_res_lines):
            rslt = {f'period{i}': 0 for i in range(len(periods))}
            for query_res in query_res_lines:
                for i in range(len(periods)):
                    rslt[f'period{i}'] += query_res[f'period{i}']
            rslt['total'] = sum(rslt[f'period{i}'] for i in range(len(periods)))
            rslt['has_sublines'] = True
            # Columna "Cont" de v15: cada apunte cae en un solo periodo, así
            # que la suma por periodo es el número de documentos del grupo.
            rslt['line_count'] = sum(query_res['line_count'] for query_res in query_res_lines)
            rslt.update(dict.fromkeys(DOCUMENT_VALUES))
            if current_groupby == 'id':
                rslt.update(self._statement_document_values(query_res_lines[0], records))
            return rslt

        if not current_groupby:
            return build_result_dict(query_res_lines)

        all_res_per_grouping_key = {}
        for query_res in query_res_lines:
            all_res_per_grouping_key.setdefault(query_res['grouping_key'], []).append(query_res)
        return [
            (grouping_key, build_result_dict(res_lines))
            for grouping_key, res_lines in all_res_per_grouping_key.items()
        ]

    def _statement_prefetch(self, query_res_lines):
        """Recordsets de todo el lote para que la lectura de nombres se haga
        con una consulta por modelo y no una por línea."""
        partner_ids, journal_ids, currency_ids, analytic_ids = set(), set(), set(), set()
        for query_res in query_res_lines:
            partner_ids.update(pid for pid in query_res['partner_id'] if pid)
            journal_ids.update(jid for jid in query_res['journal_id'] if jid)
            currency_ids.update(cid for cid in query_res['currency_id'] if cid)
            for key in (query_res['analytic_distribution'] or {}):
                analytic_ids.update(int(aid) for aid in key.split(',') if aid)
        return {
            'partner': self.env['res.partner'].browse(partner_ids),
            'journal': self.env['account.journal'].browse(journal_ids),
            'currency': self.env['res.currency'].browse(currency_ids),
            'analytic': self.env['account.analytic.account'].browse(analytic_ids).exists(),
        }

    def _statement_document_values(self, query_res, records):
        def single(key):
            values = query_res[key]
            return values[0] if values and len(values) == 1 else None

        partner = records['partner'].filtered(lambda p: p.id == single('partner_id'))
        journal = records['journal'].filtered(lambda j: j.id == single('journal_id'))
        currency = records['currency'].filtered(lambda c: c.id == single('currency_id'))
        analytic_ids = {
            int(aid)
            for key in (query_res['analytic_distribution'] or {})
            for aid in key.split(',') if aid
        }
        analytics = records['analytic'].filtered(lambda a: a.id in analytic_ids)
        id_type = partner['l10n_latam_identification_type_id'] \
            if partner and 'l10n_latam_identification_type_id' in partner._fields else None

        values = {
            'move_number': single('move_number'),
            'move_currency': currency.name or None,
            'currency_id': currency.id or None,
            'analytic_account': ', '.join(analytics.mapped('display_name')) or None,
            'identification_type': id_type.name if id_type else None,
            'identification_number': partner.vat or None,
            'invoice_ref': single('invoice_ref'),
            'country_name': partner.country_id.name or None,
            'journal_name': journal.name or None,
            'report_date': single('report_date'),
            'account': single('account'),
            'amount_invoice': single('amount_invoice'),
            'amount_residual': single('amount_residual'),
        }
        for label in OPTIONAL_MOVE_FIELDS:
            values[label] = single(label)
        return values
