# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF',
}

_logger = logging.getLogger(__name__)


class AccountAuxiliaryAnalyticWizard(models.Model):
    _name = 'account.auxiliary.analytic.wizard'
    _description = 'Auxiliary Analytic Report Wizard'

    accounts_ids = fields.Many2many(
        comodel_name='account.account', string='Cuentas Contables')
    journal_ids = fields.Many2many(
        comodel_name='account.journal', string='Diarios')
    date_from = fields.Date(
        'Desde', default=fields.Date.today(), required=True)
    date_to = fields.Date(
        'Hasta', default=fields.Date.today(), required=True)
    date_process = fields.Datetime(
        'Fecha proceso', default=fields.Datetime.now())
    line_state = fields.Boolean('Solo publicados', default=True)
    partners_ids = fields.Many2many(
        comodel_name='res.partner', string='Terceros')
    report_type = fields.Selection(
        selection=[('local', 'Local'), ('ifrs', 'NIIF')],
        default='local', required=True)
    no_zero = fields.Boolean('Omitir saldos en cero', default=True)
    analytic_account_ids = fields.Many2many(
        comodel_name='account.analytic.account',
        string='Cuentas Analíticas')
    account_by = fields.Boolean(
        'Agrupar por cuenta', default=True,
        help='Muestra totales por cuenta contable')

    # ── Acciones de exportación ────────────────────────────

    def action_confirm(self):
        """Exportar XLSX."""
        report = self.env.ref(
            'account_report.report_account_auxiliary_analytic')
        data = {'record_id': self.id}
        return report.report_action(self, data=data)

    def button_export_pdf(self):
        self.ensure_one()
        return self._export('qweb-pdf')

    def button_export_html(self):
        self.ensure_one()
        return self._export('qweb-html')

    def _export(self, report_type='qweb-pdf'):
        self.ensure_one()
        report_name = 'account_report.account_auxiliary_analytic_qweb'
        action_report = self.env['ir.actions.report'].search([
            ('report_name', '=', report_name),
            ('report_type', '=', report_type),
        ], limit=1)
        if not action_report:
            raise ValidationError(
                _('No se encontró el reporte: %s', report_name))
        return action_report.report_action(self, data={})

    # ── Cláusulas SQL comunes ──────────────────────────────

    def _companies_tuple(self):
        ids = self.env.companies.ids
        return str(tuple(ids)).replace(',)', ')')

    def _debit_col(self):
        return 'ifrs_debit' if self.report_type == 'ifrs' else 'debit'

    def _credit_col(self):
        return 'ifrs_credit' if self.report_type == 'ifrs' else 'credit'

    def _get_query_where(self):
        comp = self._companies_tuple()
        where = "AND aml.company_id IN %s" % comp

        if self.line_state:
            where += "\nAND aml.parent_state = 'posted'"
        if self.report_type == 'ifrs':
            where += "\nAND aml.ifrs_type != 'local'"
        else:
            where += "\nAND aml.ifrs_type != 'ifrs'"
        if self.accounts_ids:
            aids = str(tuple(self.accounts_ids.ids)).replace(',)', ')')
            where += "\nAND aml.account_id IN %s" % aids
        if self.journal_ids:
            jids = str(tuple(self.journal_ids.ids)).replace(',)', ')')
            where += "\nAND aml.journal_id IN %s" % jids
        if self.partners_ids:
            pids = str(tuple(self.partners_ids.ids)).replace(',)', ')')
            where += "\nAND aml.partner_id IN %s" % pids
        if self.no_zero:
            where += (
                "\nAND (COALESCE(aml.%s, 0) != 0 OR COALESCE(aml.%s, 0) != 0)"
                % (self._debit_col(), self._credit_col()))
        return where

    def _get_analytic_where(self):
        """Where extra para filtrar cuentas analíticas."""
        if not self.analytic_account_ids:
            return ""
        ids = self.analytic_account_ids.ids
        aaids = str([str(x) for x in ids])
        return "AND aml.analytic_distribution ?| ARRAY%s" % aaids

    # ── Preparación de datos ───────────────────────────────

    def prepare_data(self):
        detail = self._query_detail()
        self.env.cr.execute(detail)
        query_data = self.env.cr.dictfetchall()

        if self.account_by:
            totals = self._query_totals_by_account()
            self.env.cr.execute(totals)
            total_rows = self.env.cr.dictfetchall()
            query_data += total_rows
            query_data = sorted(
                query_data,
                key=lambda r: [
                    r.get('code') or '',
                    r.get('date') or '',
                    r.get('move') or '',
                    r.get('analytic_name') or '',
                    not r.get('bold'),
                ],
            )
            query_data = self._add_initial_final(query_data)

        return {'report_data': query_data or []}

    def _query_detail(self):
        """Detalle: una fila por (línea contable × cuenta analítica)."""
        deb = self._debit_col()
        cre = self._credit_col()
        where = self._get_query_where()
        ana_where = self._get_analytic_where()
        d_from = self.date_from.strftime('%Y-%m-%d')
        d_to = self.date_to.strftime('%Y-%m-%d')

        # Líneas CON distribución analítica
        q_with = """
        SELECT
            False AS bold,
            aa.id AS account_id,
            COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') AS code,
            COALESCE(aa.name->>'es_CO', aa.name->>'en_US') AS name,
            COALESCE(rp.name, '**') AS partner,
            rp.vat AS vat,
            COALESCE(aaa.name->>'es_CO', aaa.name->>'en_US') AS analytic_name,
            TO_CHAR(aml.date, 'YYYY/MM/DD') AS date,
            COALESCE(aj.name->>'es_CO', aj.name->>'en_US') AS journal,
            aml.move_name AS move,
            aml.name AS line,
            aml.ref AS ref,
            COALESCE((
                SELECT string_agg(po.name, ', ' ORDER BY po.name)
                FROM account_move_purchase_order_rel ampor
                INNER JOIN purchase_order po
                    ON po.id = ampor.purchase_order_id
                WHERE ampor.account_move_id = aml.move_id
            ), '') AS purchase_order,
            '' AS initial,
            COALESCE(aml.{deb}, 0) * dist.value::numeric / 100.0
                / array_length(regexp_split_to_array(dist.key, ','), 1)
                AS debit,
            COALESCE(aml.{cre}, 0) * dist.value::numeric / 100.0
                / array_length(regexp_split_to_array(dist.key, ','), 1)
                AS credit,
            '' AS final
        FROM account_move_line aml
        INNER JOIN account_account aa ON aa.id = aml.account_id
        INNER JOIN account_journal aj ON aj.id = aml.journal_id
        INNER JOIN res_company rco ON rco.id = aml.company_id
        LEFT JOIN res_partner rp ON rp.id = aml.partner_id
        CROSS JOIN LATERAL jsonb_each_text(
            aml.analytic_distribution) AS dist(key, value)
        CROSS JOIN LATERAL regexp_split_to_table(
            dist.key, ',') AS single_key
        INNER JOIN account_analytic_account aaa
            ON aaa.id = single_key::integer
        WHERE aml.analytic_distribution IS NOT NULL
          AND aml.analytic_distribution != '{{}}'::jsonb
          AND aml.date BETWEEN '{d_from}' AND '{d_to}'
          {where}
          {ana_where}
        """.format(
            deb=deb, cre=cre, d_from=d_from, d_to=d_to,
            where=where, ana_where=ana_where)

        # Si se filtra por cuentas analíticas específicas,
        # no mostrar líneas sin analítica
        if self.analytic_account_ids:
            return q_with + """
                ORDER BY code, date, move, analytic_name
            """

        # Líneas SIN distribución analítica
        q_without = """
        SELECT
            False AS bold,
            aa.id AS account_id,
            COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') AS code,
            COALESCE(aa.name->>'es_CO', aa.name->>'en_US') AS name,
            COALESCE(rp.name, '**') AS partner,
            rp.vat AS vat,
            '' AS analytic_name,
            TO_CHAR(aml.date, 'YYYY/MM/DD') AS date,
            COALESCE(aj.name->>'es_CO', aj.name->>'en_US') AS journal,
            aml.move_name AS move,
            aml.name AS line,
            aml.ref AS ref,
            COALESCE((
                SELECT string_agg(po.name, ', ' ORDER BY po.name)
                FROM account_move_purchase_order_rel ampor
                INNER JOIN purchase_order po
                    ON po.id = ampor.purchase_order_id
                WHERE ampor.account_move_id = aml.move_id
            ), '') AS purchase_order,
            '' AS initial,
            COALESCE(aml.{deb}, 0) AS debit,
            COALESCE(aml.{cre}, 0) AS credit,
            '' AS final
        FROM account_move_line aml
        INNER JOIN account_account aa ON aa.id = aml.account_id
        INNER JOIN account_journal aj ON aj.id = aml.journal_id
        INNER JOIN res_company rco ON rco.id = aml.company_id
        LEFT JOIN res_partner rp ON rp.id = aml.partner_id
        WHERE (aml.analytic_distribution IS NULL
               OR aml.analytic_distribution = '{{}}'::jsonb)
          AND aml.date BETWEEN '{d_from}' AND '{d_to}'
          {where}
        """.format(
            deb=deb, cre=cre, d_from=d_from, d_to=d_to,
            where=where)

        return """
            ({q_with}) UNION ALL ({q_without})
            ORDER BY code, date, move, analytic_name
        """.format(q_with=q_with, q_without=q_without)

    def _query_totals_by_account(self):
        """Una fila de totales por cuenta contable (bold).

        Se usan CTEs para calcular saldo inicial y final en un solo escaneo
        por CTE en lugar de una subquery correlacionada por cada cuenta,
        lo que reduce el tiempo de ejecución drásticamente con alto volumen.
        """
        deb = self._debit_col()
        cre = self._credit_col()
        where = self._get_query_where()
        d_from = self.date_from.strftime('%Y-%m-%d')
        d_to = self.date_to.strftime('%Y-%m-%d')

        # Reusar el mismo WHERE para las CTEs, cambiando el alias de tabla
        where_ib = where.replace('aml.', 'aml_ib.')
        where_fb = where.replace('aml.', 'aml_fb.')
        where_pl = where.replace('aml.', 'aml_pl.')

        query = """
        WITH period_lines AS (
            SELECT aml_pl.account_id,
                   aml_pl.company_id,
                   SUM(COALESCE(aml_pl.{deb}, 0)) AS debit,
                   SUM(COALESCE(aml_pl.{cre}, 0)) AS credit
            FROM account_move_line aml_pl
            WHERE aml_pl.date BETWEEN '{d_from}' AND '{d_to}'
            {where_pl}
            GROUP BY aml_pl.account_id, aml_pl.company_id
        ),
        initial_bal AS (
            SELECT aml_ib.account_id,
                   aml_ib.company_id,
                   SUM(COALESCE(aml_ib.{deb}, 0) - COALESCE(aml_ib.{cre}, 0)) AS initial
            FROM account_move_line aml_ib
            WHERE aml_ib.date < '{d_from}'
            {where_ib}
            GROUP BY aml_ib.account_id, aml_ib.company_id
        ),
        final_bal AS (
            SELECT aml_fb.account_id,
                   aml_fb.company_id,
                   SUM(COALESCE(aml_fb.{deb}, 0) - COALESCE(aml_fb.{cre}, 0)) AS final
            FROM account_move_line aml_fb
            WHERE aml_fb.date <= '{d_to}'
            {where_fb}
            GROUP BY aml_fb.account_id, aml_fb.company_id
        )
        SELECT
            True AS bold,
            aa.id AS account_id,
            COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') AS code,
            COALESCE(aa.name->>'es_CO', aa.name->>'en_US') AS name,
            '' AS partner,
            '' AS vat,
            '' AS analytic_name,
            TO_CHAR(DATE('{d_from}'), 'YYYY/MM/DD') AS date,
            '' AS journal,
            '' AS move,
            '' AS line,
            '' AS ref,
            '' AS purchase_order,
            COALESCE(ib.initial, 0) AS initial,
            COALESCE(pl.debit, 0) AS debit,
            COALESCE(pl.credit, 0) AS credit,
            COALESCE(fb.final, 0) AS final
        FROM period_lines pl
        INNER JOIN account_account aa ON aa.id = pl.account_id
        INNER JOIN res_company rco ON rco.id = pl.company_id
        LEFT JOIN initial_bal ib ON ib.account_id = pl.account_id
            AND ib.company_id = pl.company_id
        LEFT JOIN final_bal fb ON fb.account_id = pl.account_id
            AND fb.company_id = pl.company_id
        ORDER BY code
        """.format(
            deb=deb, cre=cre, d_from=d_from, d_to=d_to,
            where_pl=where_pl, where_ib=where_ib, where_fb=where_fb)
        return query

    def _add_initial_final(self, data):
        """Calcula saldo inicial/final acumulado por detalle."""
        initial = 0
        for ln in data:
            if ln.get('bold'):
                initial = ln.get('initial', 0)
            else:
                ln['initial'] = initial
                final = initial + (ln.get('debit') or 0) - (ln.get('credit') or 0)
                ln['final'] = final
                initial = final
        return data

    # ── Encabezado ─────────────────────────────────────────

    def prepare_header(self):
        return [
            ('code', _('Cuenta')),
            ('name', _('Nombre')),
            ('partner', _('Tercero')),
            ('vat', _('NIT')),
            ('analytic_name', _('Cuenta Analítica')),
            ('date', _('Fecha')),
            ('journal', _('Diario')),
            ('move', _('Asiento')),
            ('line', _('Detalle')),
            ('ref', _('Referencia')),
            ('purchase_order', _('Orden de Compra')),
            ('initial', _('Saldo Inicial')),
            ('debit', _('Débito')),
            ('credit', _('Crédito')),
            ('final', _('Saldo Final')),
        ]

    # ── Vista previa HTML ──────────────────────────────────

    def data_report_preview(self):
        self.ensure_one()
        header = self.prepare_header()
        data = self.prepare_data()

        html_text = '''
            <div class="act_as_table list_table" style="margin-top: 10px;"/>
            <div class="report_aux">
                <div class="act_as_table data_table">
                    <div class="act_as_thead">
                        <div class="act_as_row labels">
                            th_report
                        </div>
                    </div>
                    data_report
                </div>
            </div>
        '''

        th_text = ''.join(
            '<div class="act_as_cell" style="font-size: 13px; '
            'font-family: helvetica;">%s</div>' % label.upper()
            for _, label in header)
        html_text = html_text.replace('th_report', th_text)

        tr_text = ''
        amount_keys = ('initial', 'debit', 'credit', 'final')
        for tr_data in data.get('report_data', []):
            tr_text += '<div class="act_as_row lines">'
            bold = tr_data.get('bold', False)

            for key, _ in header:
                value = tr_data.get(key, '')
                if isinstance(value, (int, float)):
                    formatted = '{:_.2f}'.format(value).replace(
                        '.', ',').replace('_', '.')
                else:
                    formatted = str(value or '')

                css_class = ' '.join([
                    'bold-cell-report back-cell'
                    if bold else 'normal-cell-report',
                    'amount' if key in amount_keys else 'left',
                ])
                tr_text += (
                    '<div class="act_as_cell %s" style="font-size: 13px; '
                    'font-family: helvetica;">%s</div>'
                    % (css_class, formatted))

            tr_text += '</div>'

        html_text = html_text.replace('data_report', tr_text)
        return html_text
