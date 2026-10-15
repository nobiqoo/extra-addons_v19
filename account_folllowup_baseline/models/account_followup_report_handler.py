# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools import SQL


class AccountFollowupReportHandler(models.AbstractModel):
    _inherit = 'account.followup.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        """
        La carta/PDF de seguimiento (enviada o impresa desde el wizard de
        recordatorio manual) no usa account.followup.report/
        res.partner.unreconciled_aml_ids (donde sí se filtra por
        followup_account_ids/followup_excluded_journal_ids, ver
        res_partner.py). Usa este otro reporte, account_reports.followup_report,
        del motor genérico de reportes (variante del Libro Mayor de Partner),
        que arma sus propias líneas sin conocer la "Política de Seguimiento".

        Se agrega aquí el mismo filtro, vía forced_domain, con el mismo
        mecanismo que ya usa este handler para excluir líneas no_followup al
        imprimir.
        """
        super()._custom_options_initializer(report, options, previous_options)

        company = self.env.company
        forced_domain = options.get('forced_domain', [])

        # Un documento liquidado en su propia moneda no se cobra: lo que queda
        # abierto en moneda de la compañía es diferencia en cambio sin causar.
        if options.get('unreconciled'):
            forced_domain = forced_domain + [('amount_residual_currency', '!=', 0)]

        if company.followup_policy:
            if company.followup_account_ids:
                forced_domain = forced_domain + [('account_id', 'in', company.followup_account_ids.ids)]
            if company.followup_excluded_journal_ids:
                forced_domain = forced_domain + [('journal_id', 'not in', company.followup_excluded_journal_ids.ids)]

        options['forced_domain'] = forced_domain

    def _get_aml_values(self, options, partner_ids, offset=0, limit=None):
        """
        En modo "no conciliadas" (el PDF que se adjunta al cobro) cada
        documento se muestra por su saldo pendiente y no por su valor
        original, como la carta de seguimiento de la v17. El Libro Mayor de
        Partner espera descontar los pagos con sus propias líneas, pero los
        recibos y ajustes suelen estar en los diarios excluidos de la
        Política de Seguimiento: sin esto, una factura con abonos se cobra
        completa.
        """
        rslt = super()._get_aml_values(options, partner_ids, offset=offset, limit=limit)
        if not options.get('unreconciled'):
            return rslt

        aml_ids = [
            aml['id']
            for amls in rslt.values()
            for aml in amls
            if aml['key'] == 'directly_linked_aml'
        ]
        lines_by_id = {
            line.id: line
            for line in self.env['account.move.line'].browse(aml_ids)
        }

        for partner_id, amls in rslt.items():
            residual_amls = []
            for aml in amls:
                # Las líneas sin tercero conciliadas con el cliente ya están
                # descontadas en el saldo pendiente del documento.
                if aml['key'] != 'directly_linked_aml':
                    continue

                line = lines_by_id[aml['id']]
                if line.currency_id.is_zero(line.amount_residual_currency):
                    continue

                # Conserva la conversión de moneda que ya aplicó el reporte.
                rate = aml['balance'] / line.balance if line.balance else 1.0
                residual = line.amount_residual * rate
                residual_amls.append({
                    **aml,
                    'debit': max(residual, 0.0),
                    'credit': max(-residual, 0.0),
                    'amount': residual,
                    'balance': residual,
                    'amount_currency': line.amount_residual_currency,
                })
            rslt[partner_id] = residual_amls

        return rslt

    def _query_partners(self, report, options):
        """
        Los totales por cliente deben cuadrar con las líneas, que en modo
        "no conciliadas" muestran el saldo pendiente (ver _get_aml_values).
        """
        results = super()._query_partners(report, options)
        if not options.get('unreconciled'):
            return results

        residual_sums = self._get_residual_sums(report, options)
        for partner, values_by_column_group in results:
            partner_id = partner.id if partner else None
            for column_group_key, values in values_by_column_group.items():
                sums = residual_sums.get((partner_id, column_group_key), {})
                for field in ('debit', 'credit', 'amount', 'balance'):
                    values[field] = sums.get(field, 0.0)
                values['amount_currency'] = sums.get('amount_currency')
                values['currency_id'] = sums.get('currency_id')

        return results

    def _get_residual_sums(self, report, options):
        sums = {}
        company_currency = self.env.company.currency_id
        for column_group_key, group_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(group_options, 'from_beginning')
            residual = report._currency_table_apply_rate(SQL("account_move_line.amount_residual"))
            self.env.cr.execute(SQL(
                """
                SELECT account_move_line.partner_id                     AS partner_id,
                       SUM(GREATEST(%(residual)s, 0))                   AS debit,
                       SUM(GREATEST(-(%(residual)s), 0))                AS credit,
                       SUM(%(residual)s)                                AS balance,
                       CASE
                           WHEN MIN(account_move_line.currency_id) = MAX(account_move_line.currency_id)
                            AND MIN(account_move_line.currency_id) != %(company_currency)s
                           THEN MIN(account_move_line.currency_id)
                       END                                              AS currency_id,
                       CASE
                           WHEN MIN(account_move_line.currency_id) = MAX(account_move_line.currency_id)
                            AND MIN(account_move_line.currency_id) != %(company_currency)s
                           THEN SUM(account_move_line.amount_residual_currency)
                       END                                              AS amount_currency
                FROM %(table_references)s
                %(currency_table_join)s
                WHERE %(search_condition)s
                  AND account_move_line.amount_residual_currency != 0
                GROUP BY account_move_line.partner_id
                """,
                residual=residual,
                company_currency=company_currency.id,
                table_references=query.from_clause,
                currency_table_join=report._currency_table_aml_join(group_options),
                search_condition=query.where_clause,
            ))
            for row in self.env.cr.dictfetchall():
                sums[(row['partner_id'], column_group_key)] = {**row, 'amount': row['balance']}
        return sums
