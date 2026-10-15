# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF',
}


class AccountBalanceAnalyticWizard(models.Model):
    _name = 'account.balance.analytic.wizard'
    _description = 'Cost Center Balance Report Wizard'

    date_from = fields.Date(
        'Desde', default=fields.Date.today(), required=True)
    date_to = fields.Date(
        'Hasta', default=fields.Date.today(), required=True)
    date_process = fields.Datetime(
        'Fecha proceso', default=fields.Datetime.now())
    analytic_account_ids = fields.Many2many(
        comodel_name='account.analytic.account',
        string='Cuentas Analíticas',
    )
    account_ids = fields.Many2many(
        comodel_name='account.account',
        string='Cuentas Contables',
    )
    line_state = fields.Boolean('Solo publicados', default=True)
    no_zero = fields.Boolean('Omitir saldos en cero', default=True)
    show_partner = fields.Boolean('Mostrar tercero', default=False)
    report_type = fields.Selection(
        selection=[('local', 'Local'), ('ifrs', 'NIIF')],
        default='local',
        required=True,
    )

    # ── Acciones de exportación ────────────────────────────

    def action_confirm(self):
        """Exportar XLSX."""
        report = self.env.ref(
            'account_report.report_account_balance_analytic')
        data = self.prepare_data()
        return report.report_action(self, data=data)

    def button_export_pdf(self):
        self.ensure_one()
        return self._export('qweb-pdf')

    def button_export_html(self):
        self.ensure_one()
        return self._export('qweb-html')

    def _export(self, report_type='qweb-pdf'):
        self.ensure_one()
        report_name = 'account_report.account_balance_analytic_qweb'
        action_report = self.env['ir.actions.report'].search([
            ('report_name', '=', report_name),
            ('report_type', '=', report_type),
        ], limit=1)
        if not action_report:
            raise ValidationError(
                _('No se encontró el reporte: %s', report_name))
        return action_report.report_action(self, data={})

    # ── Construcción de cláusulas SQL ──────────────────────

    def _companies_tuple(self):
        ids = self.env.companies.ids
        return str(tuple(ids)).replace(',)', ')')

    def _debit_col(self):
        return 'ifrs_debit' if self.report_type == 'ifrs' else 'debit'

    def _credit_col(self):
        return 'ifrs_credit' if self.report_type == 'ifrs' else 'credit'

    def _ifrs_clause(self):
        if self.report_type == 'ifrs':
            return "AND aml.ifrs_type != 'local'"
        return "AND aml.ifrs_type != 'ifrs'"

    def _state_clause(self):
        if self.line_state:
            return "AND aml.parent_state = 'posted'"
        return ""

    def _account_clause(self):
        if not self.account_ids:
            return ""
        aids = str(tuple(self.account_ids.ids)).replace(',)', ')')
        return "AND aa.id IN %s" % aids

    def _analytic_clause(self):
        if not self.analytic_account_ids:
            return ""
        ids = str(tuple(self.analytic_account_ids.ids)).replace(',)', ')')
        return "AND single_key::integer IN %s" % ids

    def _sql_ctx(self):
        return {
            'comp': self._companies_tuple(),
            'deb': self._debit_col(),
            'cre': self._credit_col(),
            'ifrs': self._ifrs_clause(),
            'state': self._state_clause(),
            'acct': self._account_clause(),
        }

    # ── Preparación principal de datos ─────────────────────

    def prepare_data(self):
        bs = self._build_bs_data()
        pl_a = self._build_pl_analytic_data()
        pl_na = self._build_pl_no_analytic_data()

        all_data = bs + pl_a + pl_na
        all_data.sort(
            key=lambda r: (r.get('code') or '', r.get('analytic_name') or '',
                           r.get('partner') or ''))

        details = [r for r in all_data if not r.get('bold')]
        total = {
            'bold': True,
            'analytic_name': '',
            'code': '',
            'name': 'TOTAL',
            'partner': '',
            'vat': '',
            'initial': sum(r['initial'] for r in details),
            'debit': sum(r['debit'] for r in details),
            'credit': sum(r['credit'] for r in details),
            'final': sum(r['final'] for r in details),
        }
        all_data.append(total)
        return {'report_data': all_data}

    # ── Cuentas de balance (1,2,3) sin analítica ───────────

    def _build_bs_data(self):
        c = self._sql_ctx()
        d_from = self.date_from.strftime('%Y-%m-%d')
        d_to = self.date_to.strftime('%Y-%m-%d')
        sp = self.show_partner

        if sp:
            p_sel = """COALESCE(aml.partner_id, 0) AS partner_id,
                   COALESCE(rp.name, '') AS partner,
                   COALESCE(rp.vat, '') AS vat,"""
            p_join = "LEFT JOIN res_partner rp ON rp.id = aml.partner_id"
            p_grp_acct = ", aml.partner_id, rp.name, rp.vat"
            p_grp_aml = ", aml.partner_id"
            p_sel_ini = "COALESCE(aml.partner_id, 0) AS partner_id,"
        else:
            p_sel = p_join = p_grp_acct = p_grp_aml = p_sel_ini = ""

        q_accounts = """
            SELECT DISTINCT aa.id AS account_id,
                   %s
                   COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') AS code,
                   COALESCE(aa.name->>'es_CO', aa.name->>'en_US') AS name
            FROM account_move_line aml
            INNER JOIN account_account aa ON aa.id = aml.account_id
            INNER JOIN res_company rco ON rco.id = aml.company_id
            %s
            WHERE aml.date <= '%s'
              AND aml.company_id IN %s
              AND aa.include_initial_balance = true
              %s %s
            GROUP BY aa.id,
                     COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), ''),
                     aa.name %s
        """ % (p_sel, p_join, d_to, c['comp'],
               c['state'], c['acct'], p_grp_acct)

        q_initial = """
            SELECT aa.id AS account_id,
                   %s
                   SUM(aml.%s) AS debit, SUM(aml.%s) AS credit
            FROM account_move_line aml
            INNER JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.date < '%s'
              AND aml.company_id IN %s
              AND aa.include_initial_balance = true
              %s %s %s
            GROUP BY aa.id %s
        """ % (p_sel_ini, c['deb'], c['cre'], d_from, c['comp'],
               c['state'], c['ifrs'], c['acct'], p_grp_aml)

        q_period = """
            SELECT aa.id AS account_id,
                   %s
                   SUM(aml.%s) AS debit, SUM(aml.%s) AS credit
            FROM account_move_line aml
            INNER JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.date BETWEEN '%s' AND '%s'
              AND aml.company_id IN %s
              AND aa.include_initial_balance = true
              %s %s %s
            GROUP BY aa.id %s
        """ % (p_sel_ini, c['deb'], c['cre'], d_from, d_to, c['comp'],
               c['state'], c['ifrs'], c['acct'], p_grp_aml)

        self.env.cr.execute(q_accounts)
        accounts = {}
        for r in self.env.cr.dictfetchall():
            k = (r['account_id'], r['partner_id']) if sp else r['account_id']
            accounts[k] = r

        self.env.cr.execute(q_initial)
        initials = {}
        for r in self.env.cr.dictfetchall():
            k = (r['account_id'], r['partner_id']) if sp else r['account_id']
            initials[k] = r

        self.env.cr.execute(q_period)
        periods = {}
        for r in self.env.cr.dictfetchall():
            k = (r['account_id'], r['partner_id']) if sp else r['account_id']
            periods[k] = r

        result = []
        for key, acc in accounts.items():
            ini = initials.get(key, {})
            per = periods.get(key, {})
            initial_bal = (ini.get('debit') or 0) - (ini.get('credit') or 0)
            per_debit = per.get('debit') or 0
            per_credit = per.get('credit') or 0
            final_bal = initial_bal + per_debit - per_credit

            if (self.no_zero and initial_bal == 0
                    and per_debit == 0 and per_credit == 0):
                continue

            result.append({
                'bold': False,
                'analytic_name': '',
                'code': acc['code'],
                'name': acc['name'],
                'partner': acc.get('partner', '') if sp else '',
                'vat': acc.get('vat', '') if sp else '',
                'initial': initial_bal,
                'debit': per_debit,
                'credit': per_credit,
                'final': final_bal,
            })
        return result

    # ── Cuentas P&L (4,5,6,7) con analítica ───────────────

    def _build_pl_analytic_data(self):
        c = self._sql_ctx()
        ana = self._analytic_clause()
        d_from = self.date_from.strftime('%Y-%m-%d')
        d_to = self.date_to.strftime('%Y-%m-%d')
        year_start = '%s-01-01' % self.date_from.year
        sp = self.show_partner

        if sp:
            p_sel = """COALESCE(aml.partner_id, 0) AS partner_id,
                   COALESCE(rp.name, '') AS partner,
                   COALESCE(rp.vat, '') AS vat,"""
            p_join = "LEFT JOIN res_partner rp ON rp.id = aml.partner_id"
            p_sel_ini = "COALESCE(aml.partner_id, 0) AS partner_id,"
            p_grp = ", aml.partner_id"
        else:
            p_sel = p_join = p_sel_ini = p_grp = ""

        q_accounts = """
            SELECT DISTINCT
                   single_key::integer AS analytic_id,
                   COALESCE(aaa.name->>'es_CO', aaa.name->>'en_US')
                       AS analytic_name,
                   aa.id AS account_id,
                   %s
                   COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') AS code,
                   COALESCE(aa.name->>'es_CO', aa.name->>'en_US') AS name
            FROM account_move_line aml
            INNER JOIN account_account aa ON aa.id = aml.account_id
            INNER JOIN res_company rco ON rco.id = aml.company_id
            %s
            CROSS JOIN LATERAL jsonb_each_text(
                aml.analytic_distribution) AS dist(key, value)
            CROSS JOIN LATERAL regexp_split_to_table(
                dist.key, ',') AS single_key
            INNER JOIN account_analytic_account aaa
                ON aaa.id = single_key::integer
            WHERE aml.analytic_distribution IS NOT NULL
              AND aml.analytic_distribution != '{}'::jsonb
              AND aml.date <= '%s'
              AND aml.company_id IN %s
              AND aa.include_initial_balance = false
              %s %s %s
        """ % (p_sel, p_join, d_to, c['comp'],
               c['state'], c['acct'], ana)

        self.env.cr.execute(q_accounts)
        combos = self.env.cr.dictfetchall()

        def _make_key(r):
            k = (r['analytic_id'], r['account_id'])
            return k + (r['partner_id'],) if sp else k

        # Saldo inicial: año fiscal hasta date_from - 1
        if self.date_from.month == 1 and self.date_from.day == 1:
            initials = {}
        else:
            d_before = (
                self.date_from - timedelta(days=1)).strftime('%Y-%m-%d')
            q_initial = """
                SELECT single_key::integer AS analytic_id,
                       aa.id AS account_id,
                       %s
                       SUM(aml.%s * dist.value::numeric / 100.0
                           / array_length(regexp_split_to_array(
                               dist.key, ','), 1)) AS debit,
                       SUM(aml.%s * dist.value::numeric / 100.0
                           / array_length(regexp_split_to_array(
                               dist.key, ','), 1)) AS credit
                FROM account_move_line aml
                INNER JOIN account_account aa ON aa.id = aml.account_id
                CROSS JOIN LATERAL jsonb_each_text(
                    aml.analytic_distribution) AS dist(key, value)
                CROSS JOIN LATERAL regexp_split_to_table(
                    dist.key, ',') AS single_key
                WHERE aml.analytic_distribution IS NOT NULL
                  AND aml.analytic_distribution != '{}'::jsonb
                  AND aml.date BETWEEN '%s' AND '%s'
                  AND aml.company_id IN %s
                  AND aa.include_initial_balance = false
                  %s %s %s %s
                GROUP BY single_key::integer, aa.id %s
            """ % (p_sel_ini, c['deb'], c['cre'], year_start, d_before,
                   c['comp'], c['state'], c['ifrs'], c['acct'], ana,
                   p_grp)
            self.env.cr.execute(q_initial)
            initials = {}
            for r in self.env.cr.dictfetchall():
                initials[_make_key(r)] = r

        # Movimientos del período
        q_period = """
            SELECT single_key::integer AS analytic_id,
                   aa.id AS account_id,
                   %s
                   SUM(aml.%s * dist.value::numeric / 100.0
                       / array_length(regexp_split_to_array(
                           dist.key, ','), 1)) AS debit,
                   SUM(aml.%s * dist.value::numeric / 100.0
                       / array_length(regexp_split_to_array(
                           dist.key, ','), 1)) AS credit
            FROM account_move_line aml
            INNER JOIN account_account aa ON aa.id = aml.account_id
            CROSS JOIN LATERAL jsonb_each_text(
                aml.analytic_distribution) AS dist(key, value)
            CROSS JOIN LATERAL regexp_split_to_table(
                dist.key, ',') AS single_key
            WHERE aml.analytic_distribution IS NOT NULL
              AND aml.analytic_distribution != '{}'::jsonb
              AND aml.date BETWEEN '%s' AND '%s'
              AND aml.company_id IN %s
              AND aa.include_initial_balance = false
              %s %s %s %s
            GROUP BY single_key::integer, aa.id %s
        """ % (p_sel_ini, c['deb'], c['cre'], d_from, d_to, c['comp'],
               c['state'], c['ifrs'], c['acct'], ana, p_grp)
        self.env.cr.execute(q_period)
        periods = {}
        for r in self.env.cr.dictfetchall():
            periods[_make_key(r)] = r

        result = []
        for combo in combos:
            key = _make_key(combo)
            ini = initials.get(key, {})
            per = periods.get(key, {})
            initial_bal = (ini.get('debit') or 0) - (ini.get('credit') or 0)
            per_debit = per.get('debit') or 0
            per_credit = per.get('credit') or 0
            final_bal = initial_bal + per_debit - per_credit

            if (self.no_zero and initial_bal == 0
                    and per_debit == 0 and per_credit == 0):
                continue

            result.append({
                'bold': False,
                'analytic_name': combo['analytic_name'] or '',
                'code': combo['code'],
                'name': combo['name'],
                'partner': combo.get('partner', '') if sp else '',
                'vat': combo.get('vat', '') if sp else '',
                'initial': initial_bal,
                'debit': per_debit,
                'credit': per_credit,
                'final': final_bal,
            })
        return result

    # ── Cuentas P&L sin distribución analítica ─────────────

    def _build_pl_no_analytic_data(self):
        # Si se filtra por cuentas analíticas, no mostrar sin analítica
        if self.analytic_account_ids:
            return []

        c = self._sql_ctx()
        d_from = self.date_from.strftime('%Y-%m-%d')
        d_to = self.date_to.strftime('%Y-%m-%d')
        year_start = '%s-01-01' % self.date_from.year
        no_ana = ("(aml.analytic_distribution IS NULL"
                  " OR aml.analytic_distribution = '{}'::jsonb)")
        sp = self.show_partner

        if sp:
            p_sel = """COALESCE(aml.partner_id, 0) AS partner_id,
                   COALESCE(rp.name, '') AS partner,
                   COALESCE(rp.vat, '') AS vat,"""
            p_join = "LEFT JOIN res_partner rp ON rp.id = aml.partner_id"
            p_grp_acct = ", aml.partner_id, rp.name, rp.vat"
            p_grp_aml = ", aml.partner_id"
            p_sel_ini = "COALESCE(aml.partner_id, 0) AS partner_id,"
        else:
            p_sel = p_join = p_grp_acct = p_grp_aml = p_sel_ini = ""

        q_accounts = """
            SELECT DISTINCT aa.id AS account_id,
                   %s
                   COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') AS code,
                   COALESCE(aa.name->>'es_CO', aa.name->>'en_US') AS name
            FROM account_move_line aml
            INNER JOIN account_account aa ON aa.id = aml.account_id
            INNER JOIN res_company rco ON rco.id = aml.company_id
            %s
            WHERE %s
              AND aml.date <= '%s'
              AND aml.company_id IN %s
              AND aa.include_initial_balance = false
              %s %s
            GROUP BY aa.id,
                     COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), ''),
                     aa.name %s
        """ % (p_sel, p_join, no_ana, d_to, c['comp'],
               c['state'], c['acct'], p_grp_acct)

        self.env.cr.execute(q_accounts)
        accounts = {}
        for r in self.env.cr.dictfetchall():
            k = (r['account_id'], r['partner_id']) if sp else r['account_id']
            accounts[k] = r
        if not accounts:
            return []

        if self.date_from.month == 1 and self.date_from.day == 1:
            initials = {}
        else:
            d_before = (
                self.date_from - timedelta(days=1)).strftime('%Y-%m-%d')
            q_initial = """
                SELECT aa.id AS account_id,
                       %s
                       SUM(aml.%s) AS debit, SUM(aml.%s) AS credit
                FROM account_move_line aml
                INNER JOIN account_account aa ON aa.id = aml.account_id
                WHERE %s
                  AND aml.date BETWEEN '%s' AND '%s'
                  AND aml.company_id IN %s
                  AND aa.include_initial_balance = false
                  %s %s %s
                GROUP BY aa.id %s
            """ % (p_sel_ini, c['deb'], c['cre'], no_ana,
                   year_start, d_before, c['comp'],
                   c['state'], c['ifrs'], c['acct'], p_grp_aml)
            self.env.cr.execute(q_initial)
            initials = {}
            for r in self.env.cr.dictfetchall():
                k = (r['account_id'], r['partner_id']) if sp else r['account_id']
                initials[k] = r

        q_period = """
            SELECT aa.id AS account_id,
                   %s
                   SUM(aml.%s) AS debit, SUM(aml.%s) AS credit
            FROM account_move_line aml
            INNER JOIN account_account aa ON aa.id = aml.account_id
            WHERE %s
              AND aml.date BETWEEN '%s' AND '%s'
              AND aml.company_id IN %s
              AND aa.include_initial_balance = false
              %s %s %s
            GROUP BY aa.id %s
        """ % (p_sel_ini, c['deb'], c['cre'], no_ana,
               d_from, d_to, c['comp'],
               c['state'], c['ifrs'], c['acct'], p_grp_aml)
        self.env.cr.execute(q_period)
        periods = {}
        for r in self.env.cr.dictfetchall():
            k = (r['account_id'], r['partner_id']) if sp else r['account_id']
            periods[k] = r

        result = []
        for key, acc in accounts.items():
            ini = initials.get(key, {})
            per = periods.get(key, {})
            initial_bal = (ini.get('debit') or 0) - (ini.get('credit') or 0)
            per_debit = per.get('debit') or 0
            per_credit = per.get('credit') or 0
            final_bal = initial_bal + per_debit - per_credit

            if (self.no_zero and initial_bal == 0
                    and per_debit == 0 and per_credit == 0):
                continue

            result.append({
                'bold': False,
                'analytic_name': '',
                'code': acc['code'],
                'name': acc['name'],
                'partner': acc.get('partner', '') if sp else '',
                'vat': acc.get('vat', '') if sp else '',
                'initial': initial_bal,
                'debit': per_debit,
                'credit': per_credit,
                'final': final_bal,
            })
        return result

    # ── Encabezado y vista previa HTML ─────────────────────

    def prepare_header(self):
        header = [
            ('analytic_name', _('Cuenta Analítica')),
            ('code', _('Cuenta Contable')),
            ('name', _('Nombre')),
        ]
        if self.show_partner:
            header += [
                ('partner', _('Tercero')),
                ('vat', _('NIT')),
            ]
        header += [
            ('initial', _('Saldo Inicial')),
            ('debit', _('Débito')),
            ('credit', _('Crédito')),
            ('final', _('Saldo Final')),
        ]
        return header

    def data_report_preview(self):
        """Genera HTML para la vista previa QWeb (PDF/HTML)."""
        self.ensure_one()
        header = self.prepare_header()
        data = self.prepare_data()

        html_text = '''
            <div class="act_as_table list_table" style="margin-top: 10px;">
                <div class="report_aux">
                    <div class="act_as_table data_table">
                        <div class="act_as_thead">
                            <div class="act_as_row labels">
                                th_report
                            </div>
                        </div>
                        <div class="act_as_tbody">
                            data_report
                        </div>
                    </div>
                </div>
            </div>
        '''

        th_text = ''.join(
            '<div class="act_as_cell">%s</div>' % label.upper()
            for _, label in header)
        html_text = html_text.replace('th_report', th_text)

        tr_text = ''
        for tr_data in data.get('report_data', []):
            tr_text += '<div class="act_as_row lines">'
            bold = tr_data.get('bold', False)

            for key, _ in header:
                value = tr_data.get(key, '')
                if isinstance(value, (int, float)):
                    formatted = '{:,.2f}'.format(value).replace(
                        ',', '_').replace('.', ',').replace('_', '.')
                else:
                    formatted = str(value or '')

                css_class = ' '.join([
                    'bold-cell-report back-cell'
                    if bold else 'normal-cell-report',
                    'amount'
                    if key in ('initial', 'debit', 'credit', 'final')
                    else 'left',
                ])
                tr_text += (
                    '<div class="act_as_cell %s">%s</div>'
                    % (css_class, formatted)
                )

            tr_text += '</div>'

        html_text = html_text.replace('data_report', tr_text)
        return html_text
