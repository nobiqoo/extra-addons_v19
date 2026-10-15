# -*- coding: utf-8 -*-

import base64
import io

import xlwt

from odoo import fields, models
from odoo.tools import SQL

# Novedad DataCredito -> Estado de cuenta (fórmula del reporte v16)
NOVELTY_TO_ACCOUNT_STATE = {
    '01': '01',
    '05': '03',
    '06': '02',
    '07': '02',
    '08': '02',
    '09': '02',
    '12': '05',
    '13': '60',
}

PAYMENT_STATE_ES = {
    'not_paid': 'No pagadas',
    'in_payment': 'En proceso de pago',
    'paid': 'Pagado',
    'partial': 'Pagado Parcialmente',
    'reversed': 'Revertido',
    'invoicing_legacy': 'Factura Sistema Anterior',
}


class ReceivableAccountWizard(models.TransientModel):
    """Port del wizard "Generar Informes Contables" de Distritodo v16
    (custom_report_account_receivable). Genera los informes de Cartera,
    Recaudo y DataCredito en Excel. Los valores que en v16 estaban quemados
    (diario 1884, medio de pago 2, cuentas 1305%%/2805%%) salen de la
    parametrización ocr_* de la compañía."""
    _name = 'receivable.account.wizard'
    _description = 'Generar Informes Contables'

    report_type = fields.Selection(
        [('account', 'Cartera'), ('collection', 'Recaudo'),
         ('credit_data', 'DataCredito')],
        default='account', string='Tipo de Informe a Generar', required=True)
    init_date = fields.Datetime(
        string='Fecha Inicio Recaudo',
        default=lambda self: fields.Datetime.now().replace(
            day=1, hour=0, minute=0, second=0))
    end_date = fields.Datetime(
        string='Fecha Fin Recaudo', default=lambda self: fields.Datetime.now())
    journal_ids = fields.Many2many(
        'account.journal', 'account_journal_wizard_rel', 'receivable_id',
        'jornal_id', string='Diarios')
    account_ids = fields.Many2many(
        'account.account', 'account_receivable_account_wizard_rel',
        'receivable_id', 'account_id', string='Cuentas')
    account_collection_ids = fields.Many2many(
        'account.account', 'account_collection_wizard_rel', 'receivable_id',
        'account_id', string='Cuentas')
    account_credit_data_ids = fields.Many2many(
        'account.account', 'account_credit_data_wizard_rel', 'receivable_id',
        'account_id', string='Cuentas')
    partner_ids = fields.Many2many(
        'res.partner', 'partner_receivable_account_wizard_rel',
        'receivable_id', 'partner_id', string='Contactos')
    partner_tags_ids = fields.Many2many(
        'res.partner.category',
        'partner_category_receivable_account_wizard_rel', 'receivable_id',
        'partner_categ_id', string='Categorias de Contacto')

    # ------------------------------------------------------------------
    # Utilidades comunes
    # ------------------------------------------------------------------
    def _get_dates(self):
        init_date = (self.init_date or fields.Datetime.from_string(
            '0001-01-01 00:00:00')).date()
        end_date = (self.end_date or fields.Datetime.now()).date()
        return init_date, end_date

    def _base_conditions(self, end_date):
        """Condiciones comunes: asiento publicado, compañía y filtros del
        wizard (diarios, contactos, categorías)."""
        conditions = [
            SQL("m.state = 'posted'"),
            SQL("l.company_id IN %s", tuple(self.env.company.ids)),
        ]
        if self.journal_ids:
            conditions.append(SQL("m.journal_id IN %s",
                                  tuple(self.journal_ids.ids)))
        if self.partner_ids:
            conditions.append(SQL("l.partner_id IN %s",
                                  tuple(self.partner_ids.ids)))
        if self.partner_tags_ids:
            conditions.append(SQL(
                """l.partner_id IN (SELECT partner_id
                    FROM res_partner_res_partner_category_rel
                    WHERE category_id IN %s)""",
                tuple(self.partner_tags_ids.ids)))
        return conditions

    # Forma de pago contado/crédito: misma definición que usa la
    # localización (l10n_co_bloodo._compute_fe_is_direct_payment):
    # contado cuando la factura vence el mismo día (o sin vencimiento).
    CREDIT_SQL = SQL("(m.invoice_date_due IS NOT NULL"
                     " AND m.invoice_date_due > m.invoice_date)")

    def _prepare_maps(self, rows):
        """Prefetch de registros para las columnas descriptivas."""
        move_ids = {r['move_id'] for r in rows if r.get('move_id')}
        partner_ids = {r['partner_id'] for r in rows if r.get('partner_id')}
        account_ids = set()
        for row in rows:
            account_ids.update(row.get('account_ids') or [])
        return (
            {m.id: m for m in self.env['account.move'].browse(move_ids)},
            {p.id: p for p in self.env['res.partner'].browse(partner_ids)},
            {a.id: a for a in self.env['account.account'].browse(account_ids)},
        )

    def _sorted_rows(self, rows, partners):
        return sorted(rows, key=lambda r: (
            (partners[r['partner_id']].display_name or '').upper()
            if r['partner_id'] in partners else '',
            r.get('obligation') or ''))

    def _payment_mean_name(self, move):
        """Forma de pago como la mostraba v16 (CONTADO/CREDITO)."""
        if not move:
            return ''
        if move.invoice_date_due and move.invoice_date \
                and move.invoice_date_due > move.invoice_date:
            return 'CREDITO'
        return 'CONTADO'

    def _partner_phone(self, partner):
        # En Odoo 19 res.partner ya no tiene 'mobile'; se usa si algún
        # módulo lo vuelve a agregar.
        if not partner:
            return ''
        mobile = partner.mobile if 'mobile' in partner._fields else False
        return mobile or partner.phone or ''

    def _download_file(self, workbook, filename):
        archivo = io.BytesIO()
        workbook.save(archivo)
        archivo.seek(0)
        data = archivo.read()
        if not data:
            raise ValueError(
                'Error de Descarga - No se pudo generar el archivo solicitado.')
        file_id = self.env['print.file'].create(
            {'filecontent': base64.b64encode(data)})
        return {
            'res_model': 'ir.actions.act_url',
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': (
                'web/content/?model=print.file&id={0}'
                '&filename_field={1}'
                '&field=filecontent&download=true'
                '&filename={1}.xls'.format(file_id.id, filename)
            ),
        }

    def action_approve_request(self):
        self.ensure_one()
        if self.report_type == 'account':
            return self._generate_cartera()
        if self.report_type == 'collection':
            return self._generate_collection()
        return self._generate_credit_data()

    # ------------------------------------------------------------------
    # Cartera
    # ------------------------------------------------------------------
    def _generate_cartera(self):
        company = self.env.company
        init_date, end_date = self._get_dates()
        # La cartera es un corte a la fecha fin: se toma todo el histórico.
        # (En v16 el default de init_date era "ahora" y dejaba el informe
        # vacío si el usuario no borraba la fecha.)
        init_date = fields.Date.from_string('0001-01-01')
        opening_journal_id = company.ocr_opening_journal_id.id or 0

        conditions = self._base_conditions(end_date)
        conditions.append(SQL(
            "COALESCE(m.invoice_date, m.date) >= %s "
            "AND COALESCE(m.invoice_date, m.date) <= %s",
            init_date, end_date))
        if self.account_ids:
            conditions.append(SQL("l.account_id IN %s",
                                  tuple(self.account_ids.ids)))
        else:
            # CxC + anticipos (v16: receivable + 2805xx) + cuentas
            # adicionales configuradas por el cliente (cualquier tipo)
            advance_accounts = self.env['account.account']
            for prefix in company._ocr_split_param(
                    company.ocr_advance_account_prefix):
                advance_accounts |= self.env['account.account'].search(
                    [('code', '=like', prefix + '%')])
            receivable_accounts = self.env['account.account'].search(
                [('account_type', '=', 'asset_receivable')])
            all_accounts = (receivable_accounts | advance_accounts
                            | company.ocr_cartera_extra_account_ids)
            conditions.append(SQL(
                "l.account_id IN %s", tuple(all_accounts.ids) or (0,)))

        residual_sql = SQL(
            "l.balance - COALESCE(part_debit.amount, 0)"
            " + COALESCE(part_credit.amount, 0)")
        due_date_sql = SQL(
            "COALESCE(l.date_maturity, m.invoice_date_due, l.date)")
        days_sql = SQL("(%s::date - %s)", end_date, due_date_sql)
        bucket_conditions = [
            SQL("%s <= 0", days_sql),
            SQL("%s > 0 AND %s <= 30", days_sql, days_sql),
            SQL("%s > 30 AND %s <= 60", days_sql, days_sql),
            SQL("%s > 60 AND %s <= 90", days_sql, days_sql),
            SQL("%s > 90", days_sql),
        ]
        select_buckets = SQL(', ').join(
            SQL("SUM(CASE WHEN %s THEN %s ELSE 0 END) AS %s",
                condition, residual_sql, SQL.identifier('period%s' % i))
            for i, condition in enumerate(bucket_conditions))

        # En el diario de apertura cada línea es un documento consolidado:
        # se agrupa por línea para tener una fila por obligación (v16).
        obligation_sql = SQL(
            "CASE WHEN l.journal_id = %s THEN l.name ELSE m.name END",
            opening_journal_id)
        # Se agrupa además por cuenta (como v16): si un mismo asiento toca
        # dos cuentas del universo (p.ej. la cartera y su contrapartida
        # configurada como cuenta adicional), sumarlas anularía el saldo y
        # la obligación desaparecería del informe.
        query = SQL(
            """
            SELECT
                l.partner_id AS partner_id,
                l.move_id AS move_id,
                ARRAY_AGG(DISTINCT l.account_id) AS account_ids,
                %(obligation)s AS obligation,
                CASE WHEN MAX(l.journal_id) = %(opening)s
                    THEN COALESCE(MIN(l.opening_date_due),
                                  MIN(m.invoice_date), MIN(m.date))
                    ELSE MIN(m.invoice_date) END AS invoice_date,
                MIN(%(due_date)s) AS next_due_date,
                MAX(%(due_date)s) AS final_due_date,
                MAX(%(days)s) AS days_due,
                SUM(%(residual)s) AS amount_total,
                %(select_buckets)s
            FROM account_move_line l
            JOIN account_move m ON m.id = l.move_id
            LEFT JOIN LATERAL (
                SELECT SUM(part.amount) AS amount, part.debit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(end_date)s
                    AND part.debit_move_id = l.id
                GROUP BY part.debit_move_id
            ) part_debit ON TRUE
            LEFT JOIN LATERAL (
                SELECT SUM(part.amount) AS amount, part.credit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(end_date)s
                    AND part.credit_move_id = l.id
                GROUP BY part.credit_move_id
            ) part_credit ON TRUE
            WHERE %(conditions)s
            GROUP BY l.partner_id, l.move_id, l.account_id, %(obligation)s
            HAVING ABS(SUM(%(residual)s)) > 0.001
            """,
            obligation=obligation_sql,
            opening=opening_journal_id,
            due_date=due_date_sql,
            days=days_sql,
            residual=residual_sql,
            select_buckets=select_buckets,
            end_date=end_date,
            conditions=SQL(' AND ').join(conditions),
        )
        self.env.cr.execute(query)
        rows = self.env.cr.dictfetchall()
        moves, partners, accounts = self._prepare_maps(rows)

        wb = xlwt.Workbook()
        ws = wb.add_sheet('Informe de Cartera', cell_overwrite_ok=True)
        ws.write(0, 0, 'Fecha de Corte: ')
        ws.write(0, 1, str(end_date))
        headers = ['Cuenta', 'Nombre Cuenta', 'Numero Documento',
                   'Etiqueta Contacto', 'Contacto', 'Ciudad', 'Direccion',
                   'Telefono', 'Obligacion', 'Método de Pago', 'Diario',
                   'Fecha Facturas', 'Fecha Proximo Vencimiento',
                   'Fecha Vencimiento Final', 'Total cartera', 'Por Vencer',
                   'Treinta Dias', 'Sesenta Dias', 'Noventa Dias',
                   'Mas de Noventa Dias', 'Dias de Vencimiento']
        for col, header in enumerate(headers):
            ws.write(1, col, header)

        row_index = 1
        for row in self._sorted_rows(rows, partners):
            row_index += 1
            partner = partners.get(row['partner_id'])
            move = moves.get(row['move_id'])
            res_accounts = [accounts[a] for a in (row['account_ids'] or [])
                            if a in accounts]
            ws.write(row_index, 0, ', '.join(a.code for a in res_accounts))
            ws.write(row_index, 1, ', '.join(a.name for a in res_accounts))
            ws.write(row_index, 2, partner.vat if partner else '')
            ws.write(row_index, 3, ', '.join(
                partner.category_id.mapped('name')) if partner else '')
            ws.write(row_index, 4, partner.name if partner else '')
            ws.write(row_index, 5, (partner.city or (
                partner.city_id.name if partner.city_id else ''))
                if partner else '')
            ws.write(row_index, 6, partner.street if partner else '')
            ws.write(row_index, 7, self._partner_phone(partner))
            ws.write(row_index, 8, row['obligation'])
            ws.write(row_index, 9, self._payment_mean_name(move))
            ws.write(row_index, 10, move.journal_id.name if move else '')
            ws.write(row_index, 11, str(row['invoice_date'] or ''))
            ws.write(row_index, 12, str(row['next_due_date'] or ''))
            ws.write(row_index, 13, str(row['final_due_date'] or ''))
            ws.write(row_index, 14, row['amount_total'])
            for i in range(5):
                ws.write(row_index, 15 + i, row['period%s' % i])
            ws.write(row_index, 20, row['days_due'])
        return self._download_file(wb, 'Reporte de Cartera')

    # ------------------------------------------------------------------
    # Recaudo
    # ------------------------------------------------------------------
    def _generate_collection(self):
        company = self.env.company
        init_date, end_date = self._get_dates()

        conditions = self._base_conditions(end_date)
        if not self.journal_ids:
            for code in company._ocr_split_param(
                    company.ocr_collection_excluded_journal_codes):
                if code.endswith('%'):
                    conditions.append(SQL(
                        "m.journal_id NOT IN (SELECT id FROM account_journal"
                        " WHERE code LIKE %s)", code))
                else:
                    conditions.append(SQL(
                        "m.journal_id NOT IN (SELECT id FROM account_journal"
                        " WHERE code = %s)", code))
        if self.account_collection_ids:
            account_ids = self.account_collection_ids
        else:
            prefix = (company.ocr_collection_account_prefix or '').strip()
            domain = [('code', '=like', prefix + '%')] if prefix else \
                [('account_type', '=', 'asset_receivable')]
            excluded = company._ocr_split_param(
                company.ocr_collection_excluded_accounts)
            if excluded:
                domain.append(('code', 'not in', excluded))
            account_ids = self.env['account.account'].search(domain)
        conditions.append(SQL("l.account_id IN %s",
                              tuple(account_ids.ids) or (0,)))
        if not self.partner_ids:
            excluded_vats = company._ocr_split_param(
                company.ocr_excluded_partner_vats)
            if excluded_vats:
                conditions.append(SQL(
                    "l.partner_id NOT IN (SELECT id FROM res_partner"
                    " WHERE vat IN %s)", tuple(excluded_vats)))
        # Solo facturas a crédito (v16 excluía el medio de pago contado).
        # El filtro v16 por matching_number 'A%'/'P' no se replica: en Odoo
        # 18 las conciliaciones totales ya no llevan prefijo 'A' y el JOIN
        # con account_partial_reconcile ya define qué es un recaudo.
        conditions.append(self.CREDIT_SQL)

        days_sql = SQL("(part.max_date - m.invoice_date_due)")
        bucket_conditions = [
            SQL("%s <= 0", days_sql),
            SQL("%s > 0 AND %s <= 30", days_sql, days_sql),
            SQL("%s > 30 AND %s <= 60", days_sql, days_sql),
            SQL("%s > 60 AND %s <= 90", days_sql, days_sql),
            SQL("%s > 90", days_sql),
        ]
        select_buckets = SQL(', ').join(
            SQL("SUM(CASE WHEN %s THEN part.amount ELSE 0 END) AS %s",
                condition, SQL.identifier('period%s' % i))
            for i, condition in enumerate(bucket_conditions))

        query = SQL(
            """
            SELECT
                l.partner_id AS partner_id,
                l.move_id AS move_id,
                ARRAY_AGG(DISTINCT l.account_id) AS account_ids,
                MAX(m.name) AS obligation,
                ARRAY_AGG(DISTINCT payment_move.name) AS payment_names,
                MAX(m.invoice_date_due) AS due_date,
                MAX(part.max_date) AS collect_date,
                MAX(%(days)s) AS days_due,
                %(select_buckets)s
            FROM account_move_line l
            JOIN account_move m ON m.id = l.move_id
            JOIN account_partial_reconcile part
                ON part.debit_move_id = l.id
                AND part.max_date >= %(init_date)s
                AND part.max_date <= %(end_date)s
            JOIN account_move_line payment_line
                ON payment_line.id = part.credit_move_id
            JOIN account_move payment_move
                ON payment_move.id = payment_line.move_id
            WHERE %(conditions)s
            GROUP BY l.partner_id, l.move_id, l.account_id
            """,
            days=days_sql,
            select_buckets=select_buckets,
            init_date=init_date,
            end_date=end_date,
            conditions=SQL(' AND ').join(conditions),
        )
        self.env.cr.execute(query)
        rows = self.env.cr.dictfetchall()
        moves, partners, accounts = self._prepare_maps(rows)

        wb = xlwt.Workbook()
        ws = wb.add_sheet('Informe de Cartera', cell_overwrite_ok=True)
        headers = ['Fuente', 'Nombre Fuente', 'Fecha Vencimiento',
                   'Fecha Recaudo', 'Dias Vencidos', 'Cuenta', 'Nombre Cuenta',
                   'Cliente', 'Nombre Cliente', 'Factura', 'Referencia',
                   'Documento', 'Por Vencer', 'Treinta Dias', 'Sesenta Dias',
                   'Noventa Dias', 'Mas de Noventa Dias']
        for col, header in enumerate(headers):
            ws.write(0, col, header)

        row_index = 0
        for row in self._sorted_rows(rows, partners):
            row_index += 1
            partner = partners.get(row['partner_id'])
            move = moves.get(row['move_id'])
            res_accounts = [accounts[a] for a in (row['account_ids'] or [])
                            if a in accounts]
            ws.write(row_index, 0, move.journal_id.code if move else '')
            ws.write(row_index, 1, move.journal_id.name if move else '')
            ws.write(row_index, 2, str(row['due_date'] or ''))
            ws.write(row_index, 3, str(row['collect_date'] or ''))
            ws.write(row_index, 4, row['days_due'])
            ws.write(row_index, 5, ', '.join(a.code for a in res_accounts))
            ws.write(row_index, 6, ', '.join(a.name for a in res_accounts))
            ws.write(row_index, 7, partner.vat if partner else '')
            ws.write(row_index, 8, partner.name if partner else '')
            ws.write(row_index, 9, move.name if move else '')
            ws.write(row_index, 10, move.invoice_origin if move else '')
            ws.write(row_index, 11, ', '.join(
                n for n in (row['payment_names'] or []) if n))
            for i in range(5):
                ws.write(row_index, 12 + i, row['period%s' % i])
        return self._download_file(wb, 'Reporte de Recaudo')

    # ------------------------------------------------------------------
    # DataCredito
    # ------------------------------------------------------------------
    def _generate_credit_data(self):
        company = self.env.company
        init_date, end_date = self._get_dates()
        init_date = fields.Date.from_string('0001-01-01')  # v16: sin inicio
        opening_journal_id = company.ocr_opening_journal_id.id or 0

        conditions = self._base_conditions(end_date)
        conditions.append(SQL(
            "COALESCE(m.invoice_date, m.date) >= %s "
            "AND COALESCE(m.invoice_date, m.date) <= %s",
            init_date, end_date))
        if self.account_credit_data_ids:
            account_ids = self.account_credit_data_ids
        else:
            domain = [('account_type', '=', 'asset_receivable')]
            excluded = company._ocr_split_param(
                company.ocr_datacredito_excluded_accounts)
            if excluded:
                domain.append(('code', 'not in', excluded))
            for prefix in company._ocr_split_param(
                    company.ocr_datacredito_excluded_prefixes):
                domain.extend(['!', ('code', '=like', prefix + '%')])
            account_ids = self.env['account.account'].search(domain)
        conditions.append(SQL("l.account_id IN %s",
                              tuple(account_ids.ids) or (0,)))
        # Facturas a crédito, más saldos iniciales del diario de apertura
        credit_condition = SQL("(%s AND l.balance > 0)", self.CREDIT_SQL)
        if opening_journal_id:
            conditions.append(SQL(
                "((m.journal_id != %s AND %s)"
                " OR (m.journal_id = %s AND l.balance >= 0))",
                opening_journal_id, credit_condition, opening_journal_id))
        else:
            conditions.append(credit_condition)

        gross_sql = SQL(
            """CASE WHEN MAX(l.journal_id) = %(opening)s
                THEN SUM(l.balance) ELSE MAX(m.amount_total) END""",
            opening=opening_journal_id)
        paid_sql = SQL("SUM(COALESCE(part_debit.amount, 0))")
        residual_sql = SQL("(%s - %s)", gross_sql, paid_sql)
        due_sql = SQL("MAX(l.date_maturity)")
        days_over_sql = SQL(
            """CASE WHEN (%(end)s::date - %(due)s) > 0 AND %(residual)s > 0.001
                THEN (%(end)s::date - %(due)s) ELSE 0 END""",
            end=end_date, due=due_sql, residual=residual_sql)

        # En el diario de apertura cada línea es un documento consolidado:
        # se agrupa por línea para tener una fila por obligación (v16).
        obligation_sql = SQL(
            "CASE WHEN l.journal_id = %s THEN l.name ELSE m.name END",
            opening_journal_id)
        # Se agrupa además por cuenta (como v16): si un mismo asiento toca
        # dos cuentas del universo (p.ej. la cartera y su contrapartida
        # configurada como cuenta adicional), sumarlas anularía el saldo y
        # la obligación desaparecería del informe.
        query = SQL(
            """
            SELECT
                l.partner_id AS partner_id,
                l.move_id AS move_id,
                ARRAY_AGG(DISTINCT l.account_id) AS account_ids,
                %(obligation)s AS obligation,
                CASE WHEN MAX(l.journal_id) = %(opening)s
                    THEN COALESCE(MIN(l.opening_date_due),
                                  MIN(m.invoice_date), MIN(m.date))
                    ELSE MIN(m.invoice_date) END AS opening_date,
                COALESCE(MAX(l.date_maturity), MAX(m.invoice_date_due))
                    AS due_date,
                %(days_over)s AS days_over,
                %(gross)s AS initial_value,
                %(residual)s AS balance_due,
                MAX(l.balance) AS monthly_fee,
                (CASE WHEN %(due)s IS NOT NULL THEN
                    (CASE WHEN (%(end)s::date - %(due)s) > 0
                        THEN SUM(l.balance) / COUNT(l.id) ELSE 0 END)
                 ELSE SUM(l.balance) / COUNT(l.id) END
                 - %(paid)s) AS arrears_balance,
                CASE
                    WHEN %(residual)s <= 0.001 THEN '05'
                    WHEN %(days_over)s <= 0 THEN '01'
                    WHEN %(days_over)s <= 30 THEN '06'
                    WHEN %(days_over)s <= 60 THEN '07'
                    WHEN %(days_over)s <= 90 THEN '08'
                    ELSE '09' END AS novelty,
                COUNT(DISTINCT l.id) AS total_installments,
                COUNT(DISTINCT l.id) FILTER (
                    WHERE l.balance - COALESCE(part_debit.amount, 0) <= 0
                ) AS paid_installments,
                COUNT(DISTINCT l.id) FILTER (
                    WHERE l.balance - COALESCE(part_debit.amount, 0) <= 0
                    OR (%(end)s::date - COALESCE(l.date_maturity,
                        m.invoice_date_due)) > 0
                ) AS due_installments,
                MAX(part_debit.last_pay) AS last_payment_date
            FROM account_move_line l
            JOIN account_move m ON m.id = l.move_id
            LEFT JOIN LATERAL (
                SELECT
                    SUM(part.amount) AS amount,
                    MAX(part.max_date) AS last_pay,
                    part.debit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(end)s
                    AND part.debit_move_id = l.id
                GROUP BY part.debit_move_id
            ) part_debit ON TRUE
            WHERE %(conditions)s
            GROUP BY l.partner_id, l.move_id, l.account_id, %(obligation)s
            """,
            obligation=obligation_sql,
            opening=opening_journal_id,
            days_over=days_over_sql,
            gross=gross_sql,
            residual=residual_sql,
            paid=paid_sql,
            due=due_sql,
            end=end_date,
            conditions=SQL(' AND ').join(conditions),
        )
        self.env.cr.execute(query)
        rows = self.env.cr.dictfetchall()
        moves, partners, accounts = self._prepare_maps(rows)

        wb = xlwt.Workbook()
        ws = wb.add_sheet('Informe de Data Credito', cell_overwrite_ok=True)
        ws.write(0, 0, 'Fecha de Corte: ')
        ws.write(0, 1, str(end_date))
        headers = [
            'Tipo de Identificacion', 'Numero Identificacion',
            'Numero de Cuenta U Obligacion', 'Nombre Completo',
            'Situacion del Titular', 'Fecha Apertura', 'Fecha Vencimiento',
            'Responsable', 'Forma de Pago', 'Novedad',
            'Estado Origen de la cuenta', 'Fecha Estado de Origen',
            'Estado de Cuenta', 'Fecha Estado de cuenta', 'Adjetivo',
            'Fecha Adjetivo', 'Calificacion', 'Edad de Mora', 'Valor Inicial',
            'Valor Saldo Deuda', 'Valor Disponible', 'V Cuota Mensual',
            'Valor Saldo Mora', 'Total Cuotas', 'Cuotas Canceladas',
            'Cuotas En Mora', 'Clausula de Permanencia',
            'Fecha Limite de Pago', 'Fecha de Pago', 'Ciudad Correspondencia',
            'Codigo Dane Ciudad Correspondencia',
            'Departamento Correspondencia', 'Direccion de Correspondencia',
            'Correo Electronico', 'Celular', 'Cuenta', 'Diario',
            'Metodo de pago', 'Aliado', 'Estado de pago', 'Plazo de pago']
        for col, header in enumerate(headers):
            ws.write(1, col, header)

        city_has_dane = 'dian_code' in self.env['res.city']._fields
        row_index = 1
        for row in self._sorted_rows(rows, partners):
            # v16: las obligaciones saldadas solo se reportan el mes del pago
            if row['novelty'] == '05':
                last_pay = row['last_payment_date']
                if not last_pay or last_pay.month != end_date.month \
                        or last_pay.year != end_date.year:
                    continue
            row_index += 1
            partner = partners.get(row['partner_id'])
            move = moves.get(row['move_id'])
            res_accounts = [accounts[a] for a in (row['account_ids'] or [])
                            if a in accounts]
            city = partner.city_id if partner else None
            doc_type = ''
            if partner and 'l10n_latam_identification_type_id' in \
                    partner._fields and partner.l10n_latam_identification_type_id:
                doc_type = getattr(partner.l10n_latam_identification_type_id,
                                   'l10n_co_document_code', '') or ''
            balance_due = max(row['balance_due'] or 0, 0)
            arrears = row['arrears_balance'] or 0
            if arrears < 0.001:
                arrears = 0
            due_installments = 0 if balance_due <= 0 \
                else row['due_installments'] or 0
            ws.write(row_index, 0, doc_type)
            ws.write(row_index, 1, partner.vat if partner else '')
            ws.write(row_index, 2, row['obligation'])
            ws.write(row_index, 3, partner.name if partner else '')
            ws.write(row_index, 4, 0)
            ws.write(row_index, 5, str(row['opening_date'] or ''))
            ws.write(row_index, 6, str(row['due_date'] or ''))
            ws.write(row_index, 7, 0)
            ws.write(row_index, 8, '00')
            ws.write(row_index, 9, row['novelty'])
            ws.write(row_index, 10, 0)
            ws.write(row_index, 11, str(row['opening_date'] or ''))
            ws.write(row_index, 12, NOVELTY_TO_ACCOUNT_STATE.get(
                row['novelty'], ''))
            ws.write(row_index, 13, str(end_date))
            ws.write(row_index, 14, 0)
            ws.write(row_index, 15, str(end_date))
            ws.write(row_index, 16, 0)
            ws.write(row_index, 17, str(row['days_over']))
            ws.write(row_index, 18, row['initial_value'])
            ws.write(row_index, 19, balance_due)
            ws.write(row_index, 20, 0)
            ws.write(row_index, 21, row['monthly_fee'])
            ws.write(row_index, 22, arrears)
            ws.write(row_index, 23, row['total_installments'])
            ws.write(row_index, 24, row['paid_installments'])
            ws.write(row_index, 25, due_installments)
            ws.write(row_index, 26, 0)
            ws.write(row_index, 27, str(end_date))
            ws.write(row_index, 28, str(row['last_payment_date'] or ''))
            ws.write(row_index, 29, (partner.city or (
                city.name if city else '')) if partner else '')
            ws.write(row_index, 30, ('%s000' % city.dian_code)
                     if city and city_has_dane and city.dian_code else '')
            ws.write(row_index, 31, partner.state_id.name
                     if partner and partner.state_id else '')
            ws.write(row_index, 32, partner.street if partner else '')
            ws.write(row_index, 33, partner.email if partner else '')
            ws.write(row_index, 34, self._partner_phone(partner))
            ws.write(row_index, 35, ', '.join(a.code for a in res_accounts))
            ws.write(row_index, 36, move.journal_id.name if move else '')
            ws.write(row_index, 37, self._payment_mean_name(move))
            ws.write(row_index, 38, '')
            ws.write(row_index, 39, PAYMENT_STATE_ES.get(
                move.payment_state, move.payment_state) if move else '')
            ws.write(row_index, 40, move.invoice_payment_term_id.name
                     if move and move.invoice_payment_term_id else '')
        return self._download_file(wb, 'Reporte de DataCredito')


class PrintFile(models.TransientModel):
    _name = 'print.file'
    _description = 'Documentos para descargar'

    filecontent = fields.Binary(string='Impresión')
