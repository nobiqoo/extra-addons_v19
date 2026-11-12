# -*- coding: utf-8 -*-

import logging
from html import escape

from odoo import _, fields, models, api
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF'
}

_logger = logging.getLogger(__name__)

# Máximo de líneas para generar el PDF (0 = sin límite)
PDF_MAX_ROWS = 15000


class AccountauxiliaryWizard(models.Model):
    _name = 'account.auxiliary.wizard'
    _description = 'Auxiliary Report Wizard'

    accounts_ids = fields.Many2many(comodel_name='account.account',
                                    string='Accounts')
    journal_ids = fields.Many2many(comodel_name='account.journal',
                                   string='Diarios')
    currency_by = fields.Boolean('Multi-currency?',
                                 default=False,)
    date_from = fields.Date('From',
                            default=fields.Date.today())
    date_to = fields.Date('To',
                          default=fields.Date.today())
    date_process = fields.Datetime('Fecha proceso',
                                   default=fields.Datetime.now())
    group_by = fields.Boolean('By account and partner',
                              default=False,
                              help='Totals per account')
    line_state = fields.Boolean('Posted?',
                                default=True)
    partner_by = fields.Boolean('By partner',
                                help='Totals per partner')
    account_by = fields.Boolean('By account',
                                help='Totals per partner')
    partners_ids = fields.Many2many(comodel_name='res.partner',
                                    string='Partners')
    report_type = fields.Selection(selection=[('local', 'Local'),
                                              ('ifrs', 'IFRS')],
                                   default='local',
                                   required=True)
    group_by_partner = fields.Boolean('Group by partner',
                                      default=False,)
    no_zero = fields.Boolean('Skip zero balances',
                             default=True)
    account_analytic_ids = fields.Many2many(comodel_name='account.analytic.account',
                                            string='Cuentas Analiticas')
    account_analytic = fields.Boolean('Cuenta analítica?', default=False)

    @api.onchange('partner_by')
    def onchange_partner_by(self):
        if self.partner_by:
            self.account_by = False
            self.group_by = False
        else:
            pass

    @api.onchange('account_by')
    def onchange_account_by(self):
        if self.account_by:
            self.group_by = False
            self.partner_by = False
        else:
            pass

    @api.onchange('group_by')
    def onchange_group_by(self):
        if self.group_by:
            self.account_by = False
            self.partner_by = False
        else:
            pass

    def action_confirm(self):
        report = self.env.ref('account_report.report_account_auxiliary')
        data = {'record_id': self.id}
        return report.report_action(self, data=data)

    def button_export_pdf(self):
        self.ensure_one()
        self._check_pdf_max_rows()
        report_type = 'qweb-pdf'
        return self._export(report_type)

    def _check_pdf_max_rows(self):
        """Evita generar PDF de reportes demasiado grandes.

        wkhtmltopdf falla o agota la memoria del servidor con decenas de miles
        de filas; en ese caso se pide usar el Excel o acotar el reporte. El
        tope se puede ajustar con el parámetro de sistema
        `account_report.pdf_max_rows`.
        """
        max_rows = int(self.env['ir.config_parameter'].sudo().get_param(
            'account_report.pdf_max_rows', PDF_MAX_ROWS))
        if not max_rows:
            return
        self.env.cr.execute(
            'select count(*) from (' + self.prepare_data_detail() + ') q')
        rows = self.env.cr.fetchone()[0]
        if rows > max_rows:
            raise ValidationError(_(
                'El reporte tiene %(rows)s líneas y el PDF admite hasta '
                '%(max)s. Use la opción EXCEL o acote el rango de fechas, '
                'las cuentas o los terceros.', rows=rows, max=max_rows))

    def button_preview_html(self):
        self.ensure_one()
        report_type = 'qweb-html'
        return self._export(report_type)

    def _export(self, report_type='qweb-pdf'):
        '''Default export is PDF.'''
        report_name = 'account_report.account_auxiliary_qweb'
        self.ensure_one()
        action_report = self.env['ir.actions.report'].search(
            [
                ('report_name', '=', report_name),
                ('report_type', '=', report_type)
            ],
            limit=1,
        )
        if not action_report:
            raise ValidationError(
                _('Not found report ID: %s', report_name))
        data_report = {}
        out = action_report.report_action(self, data=data_report)
        return out

    def prepare_data(self):
        query_data_detail = self.prepare_data_detail()
        query_data_acc_rp = self.prepare_data_acc_rp()
        query_data_acc = self.prepare_data_acc()
        query_data_rp = self.prepare_data_rp()

        data_detail = self._execute_query(query_data_detail)
        query_data = data_detail
        if self.group_by:
            data_acc_rp = self._execute_query(query_data_acc_rp)
            data_acc = self._execute_query(query_data_acc)
            query_data += data_acc_rp
            query_data += data_acc
            query_data = sorted(
                query_data,
                key=lambda r: [r['code'], r['partner'],
                               r['date'], r['move'], not r['bold']]
            )
            query_data = self._add_initial_final(query_data)
        if self.account_by:
            data_acc = self._execute_query(query_data_acc)
            query_data += data_acc
            query_data = sorted(
                query_data,
                key=lambda r: [r['code'], r['date'], r['move'], not r['bold']]
            )
            query_data = self._add_initial_final(query_data)
        if self.partner_by:
            data_rp = self._execute_query(query_data_rp)
            query_data += data_rp
            query_data = sorted(
                query_data,
                key=lambda r: [r['partner'], r['code'],
                               r['date'], r['move'], not r['bold']]
            )
            query_data = self._add_initial_final(query_data)
        return {'report_data': query_data and query_data or []}

    def _execute_query(self, query):
        self.env.cr.execute(query)
        data_query = self.env.cr.dictfetchall()
        return data_query

    def prepare_data_detail(self):
        query = """
        select
            False as bold,
            False as group,
            aa.id as account_id,
            COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') as code,
            COALESCE(aa.name->'es_CO', aa.name->'en_US') as name,
            rp.vat as vat,
            coalesce(rp.name, '**') as partner,
            coalesce(rc_line.name->>'en_US', rc_move.name->>'en_US') as city,
            TO_CHAR(aml.date, 'YYYY/MM/DD') as date,
            COALESCE(aj.name->'es_CO', aj.name->'en_US') as journal,
        """
        if self.account_analytic:
            query += """
                STRING_AGG(COALESCE(an.name->>'es_CO', an.name->>'en_US'), '; ') AS analytic,
            """
        query += """
            am.name as move,
            aml.name as line,
        """

        if self.currency_by:
            query += """
                rc.name as currency,
                aml.amount_currency as amount,
            """

        query += """
            '' as initial,
            coalesce(aml.{debit}, 0) as debit,
            coalesce(aml.{credit}, 0) as credit,
            '' as final
        from account_move_line aml
        inner join account_account aa on aa.id = aml.account_id
        inner join res_company rco on rco.id = aml.company_id
        inner join account_move am on am.id = aml.move_id
        inner join account_journal aj on aj.id = aml.journal_id
        left join res_partner rp on rp.id = aml.partner_id
        left join res_city rc_line on rc_line.id = aml.city_id  
        left join res_city rc_move on rc_move.id = am.city_id 
        """.format(
            credit=self.report_type == 'local' and 'credit' or 'ifrs_credit',
            debit=self.report_type == 'local' and 'debit' or 'ifrs_debit',
            date_start=self.date_from,
            date_end=self.date_to
        )

        if self.account_analytic:
            query += """
                LEFT JOIN account_analytic_account an ON an.id::text in (select jsonb_object_keys(aml.analytic_distribution))
                """
        if self.currency_by:
            query += """
            left join res_currency rc on rc.id = aml.currency_id
            """

        query += """
        where aml.date between '%s' and '%s'
        %s
        """ % (
            self.date_from,
            self.date_to,
            self._get_query_where()
        )
        if self.account_analytic:
            query += """
                GROUP BY aml.id, aa.id, rco.id, rp.vat, rp.name, aj.name, am.name, rc_line.name, rc_move.name, am.ref
                """

        query += """
        order by COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), ''), rp.name, aml.date
        """
        if self.partner_by and 1 == 0:
            query = query.replace(
                "'' as initial",
                '''coalesce((
                    select sum(aml2.{debit} - aml2.{credit})
                    from account_move_line as aml2
                    inner join account_move am2 on am2.id = aml2.move_id
                    where aml2.account_id = aa.id
                    and (
                        aml2.partner_id = aml.partner_id
                        or
                        (
                            aml2.partner_id is null
                            and
                            aml.partner_id is null
                        )
                    )
                    and aml2.date < '{date_start}'
                    {where2}
                ), 0) as initial,
                '''
            ).replace(
                "'' as final",
                '''coalesce((
                select sum(aml2.{debit} - aml2.{credit})
                from account_move_line as aml2
                inner join account_move am2 on am2.id = aml2.move_id
                where aml2.account_id = aa.id
                and (
                    aml2.partner_id = aml.partner_id
                    or
                    (
                        aml2.partner_id is null
                        and
                        aml.partner_id is null
                    )
                )
                and aml2.date <= '{date_end}'
                {where2}
            ), 0) as final
                '''
            ).format(
                credit=self.report_type == 'local' and 'credit' or 'ifrs_credit',
                debit=self.report_type == 'local' and 'debit' or 'ifrs_debit',
                date_start=self.date_from,
                date_end=self.date_to,
                where=self._get_query_where(),
                where2=self._get_query_where2()
            )
        # print(query)
        return query

    def _get_query_where(self):
        ids_companies = self.env.companies.ids
        ids_companies = str(tuple(ids_companies)).replace(',)', ')')
        where = 'and aml.company_id in %s' % ids_companies

        if self.line_state:
            where += """
                and aml.parent_state = 'posted'
            """
        if self.report_type == 'ifrs':
            where += """
                and aml.ifrs_type != 'local'
            """
        else:
            where += """
                and aml.ifrs_type != 'ifrs'
            """
        if self.accounts_ids:
            accounts_ids = self.accounts_ids.ids
            aids = str(tuple(accounts_ids)).replace(',)', ')')
            where += """
            and aml.account_id in %s
            """ % aids
        if self.journal_ids:
            journal_ids = self.journal_ids.ids
            jids = str(tuple(journal_ids)).replace(',)', ')')
            where += '''
            AND aml.journal_id in %s
            ''' % jids
        if self.partners_ids:
            partners_ids = self.partners_ids.ids
            pids = str(tuple(partners_ids)).replace(',)', ')')
            where += """
            and aml.partner_id in %s
            """ % pids
        if self.account_analytic and self.account_analytic_ids:
            account_analytic_ids = self.account_analytic_ids.ids
            aaids = str([str(x) for x in account_analytic_ids])
            where += """
            AND aml.analytic_distribution ?| ARRAY%s
            """ % aaids

        if self.no_zero:
            where += """
            and coalesce(aml.{debit}, 0) - coalesce(aml.{credit}, 0) != 0
            """.format(
                debit=self.report_type == 'ifrs' and 'ifrs_debit' or 'debit',
                credit=self.report_type == 'ifrs' and 'ifrs_credit' or 'credit')
        return where

    def _get_query_where2(self):
        where = self._get_query_where()
        where = where.replace('aml', 'aml2')
        return where

    def prepare_data_acc_rp(self):
        query = """
        select
            True as bold,
            False as group,
            aa.id as account_id,
            COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') as code,
            COALESCE(aa.name->'es_CO', aa.name->'en_US') as name,
            rp.vat as vat,
            coalesce(rp.name, '**') as partner,
            coalesce(rc_line.name->>'en_US', rc_move.name->>'en_US') as city,
            TO_CHAR(DATE('{date_start}'), 'YYYY/MM/DD') as date,
            '' as journal,
        """

        if self.account_analytic:
            query += """
                '' as analytic,
            """

        query += """
            '' as move,
            '' as line,
        """

        if self.currency_by:
            query += """
                '' as currency,
                '' as amount,
            """

        query += """
            coalesce(h.initial, 0) as initial,
            sum(coalesce(aml.{debit}, 0)) as debit,
            sum(coalesce(aml.{credit}, 0)) as credit,
            coalesce(h.final, 0) as final
        from account_move_line aml
        inner join account_account aa on aa.id = aml.account_id
        inner join res_company rco on rco.id = aml.company_id
        inner join account_move am on am.id = aml.move_id
        left join res_partner rp on rp.id = aml.partner_id
        left join res_city rc_line on rc_line.id = aml.city_id 
        left join res_city rc_move on rc_move.id = am.city_id 
        left join (
            select aml2.account_id, aml2.partner_id,
                SPLIT_PART(rco2.parent_path, '/', 1) as root_id,
                sum(case when aml2.date < '{date_start}'
                    then aml2.{debit} - aml2.{credit} end) as initial,
                sum(aml2.{debit} - aml2.{credit}) as final
            from account_move_line aml2
            inner join res_company rco2 on rco2.id = aml2.company_id
            where aml2.date <= '{date_end}'
            {where2}
            group by aml2.account_id, aml2.partner_id,
                SPLIT_PART(rco2.parent_path, '/', 1)
        ) h on h.account_id = aa.id
            and coalesce(h.partner_id, 0) = coalesce(aml.partner_id, 0)
            and h.root_id = SPLIT_PART(rco.parent_path, '/', 1)
        where aml.date between '{date_start}' and '{date_end}'
        {where}
        """
        query = query.format(
            credit=self.report_type == 'local' and 'credit' or 'ifrs_credit',
            debit=self.report_type == 'local' and 'debit' or 'ifrs_debit',
            date_start=self.date_from,
            date_end=self.date_to,
            where=self._get_query_where(),
            where2=self._get_query_where2(),
            company_id=str(self.env.company.id)
        )

        query += """
        group by COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), ''), aa.id, aml.partner_id, rp.vat, rp.name, rc_line.name, rc_move.name, h.initial, h.final
        order by COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), ''), rp.name
        """
        return query

    def prepare_data_acc(self):
        query = """
        select
            True as bold,
            False as group,
            aa.id as account_id,
            COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') as code,
            COALESCE(aa.name->'es_CO', aa.name->'en_US') as name,
            '' as vat,
            '' as partner,
            coalesce(rc_line.name->>'en_US', rc_move.name->>'en_US') as city,
            TO_CHAR(DATE('{date_start}'), 'YYYY/MM/DD') as date,
            '' as journal,
        """

        if self.account_analytic:
            query += """
                '' as analytic,
            """
        query += """
            '' as move,
            '' as line,
        """

        if self.currency_by:
            query += """
                '' as currency,
                '' as amount,
            """

        query += """
            coalesce(h.initial, 0) as initial,
            sum(coalesce(aml.{debit}, 0)) as debit,
            sum(coalesce(aml.{credit}, 0)) as credit,
            coalesce(h.final, 0) as final
        from account_move_line aml
        inner join account_account aa on aa.id = aml.account_id
        inner join res_company rco on rco.id = aml.company_id
        inner join account_move am on am.id = aml.move_id
        left join res_city rc_line on rc_line.id = aml.city_id 
        left join res_city rc_move on rc_move.id = am.city_id 
        left join (
            select aml2.account_id,
                SPLIT_PART(rco2.parent_path, '/', 1) as root_id,
                sum(case when aml2.date < '{date_start}'
                    then aml2.{debit} - aml2.{credit} end) as initial,
                sum(aml2.{debit} - aml2.{credit}) as final
            from account_move_line aml2
            inner join res_company rco2 on rco2.id = aml2.company_id
            where aml2.date <= '{date_end}'
            {where2}
            group by aml2.account_id, SPLIT_PART(rco2.parent_path, '/', 1)
        ) h on h.account_id = aa.id
            and h.root_id = SPLIT_PART(rco.parent_path, '/', 1)
        where aml.date between '{date_start}' and '{date_end}'
        {where}
        """
        query = query.format(
            credit=self.report_type == 'local' and 'credit' or 'ifrs_credit',
            debit=self.report_type == 'local' and 'debit' or 'ifrs_debit',
            date_start=self.date_from,
            date_end=self.date_to,
            where=self._get_query_where(),
            where2=self._get_query_where2(),
            company_id=str(self.env.company.id)
        )
        query += """
        group by COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), ''), aa.id, rc_line.name, rc_move.name, h.initial, h.final
        order by COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '')
        """
        return query

    def prepare_data_rp(self):
        query = """
        select
            True as bold,
            False as group,
            -- aa.id as account_id,
            -- COALESCE(
            -- aa.code_store->>'{company_id}', 
            -- aa.code_store->>'1', 
            --  aa.code_store::text
            --) as code,
            -- COALESCE(aa.name->'es_CO', aa.name->'en_US') as name,
            '' as account_id,
            '' as code,
            '' as name,
            rp.vat as vat,
            coalesce(rp.name, '**') as partner,
            coalesce(rc_line.name->>'en_US', rc_move.name->>'en_US') as city,
            TO_CHAR(DATE('{date_start}'), 'YYYY/MM/DD') as date,
            '' as journal,
        """
        if self.account_analytic:
            query += """
                '' as analytic,
            """

        query += """
            '' as move,
            '' as line,
        """

        if self.currency_by:
            query += """
                '' as currency,
                '' as amount,
            """

        query += """
            coalesce(h.initial, 0) as initial,
            sum(coalesce(aml.{debit}, 0)) as debit,
            sum(coalesce(aml.{credit}, 0)) as credit,
            coalesce(h.final, 0) as final
        from account_move_line aml
        inner join account_account aa on aa.id = aml.account_id
        inner join account_move am on am.id = aml.move_id
        left join res_partner rp on rp.id = aml.partner_id
        left join res_city rc_line on rc_line.id = aml.city_id  
        left join res_city rc_move on rc_move.id = am.city_id 
        left join (
            select aml2.partner_id,
                sum(case when aml2.date < '{date_start}'
                    then aml2.{debit} - aml2.{credit} end) as initial,
                sum(aml2.{debit} - aml2.{credit}) as final
            from account_move_line aml2
            where aml2.date <= '{date_end}'
            {where2}
            group by aml2.partner_id
        ) h on coalesce(h.partner_id, 0) = coalesce(aml.partner_id, 0)
        where aml.date between '{date_start}' and '{date_end}'
            {where}
        """
        query = query.format(
            credit=self.report_type == 'local' and 'credit' or 'ifrs_credit',
            debit=self.report_type == 'local' and 'debit' or 'ifrs_debit',
            date_start=self.date_from,
            date_end=self.date_to,
            where=self._get_query_where(),
            where2=self._get_query_where2(),
            company_id=str(self.env.company.id)
        )

        query += """
        group by aml.partner_id, rp.vat, rp.name, rc_line.name, rc_move.name, h.initial, h.final
        order by rp.name
        """
        return query

    def _add_initial_final(self, data):
        initial = 0
        final = 0
        for ln in data:
            # print(ln)
            if ln.get('bold'):
                initial = ln.get('initial', 0)
            else:
                ln['initial'] = initial
                final = initial + ln.get('debit') - ln.get('credit')
                ln['final'] = final
                initial = final
        return data

    def data_report_preview(self):
        """HTML del libro auxiliar (vista previa y PDF).

        Usa una <table> real con los estilos en una hoja de estilo en vez de
        un <div> con estilo propio por celda: el HTML pesa ~6 veces menos y
        Odoo puede partir las tablas grandes para wkhtmltopdf.
        """
        self.ensure_one()
        header = self.prepare_header()
        data = self.prepare_data()

        amount_keys = ('initial', 'debit', 'credit', 'final')
        skip_keys = ('bold', 'group', 'account_id')
        out = [
            '<style>'
            'table.report_aux{width:100%;border-collapse:collapse;'
            'margin-top:10px;font:13px helvetica}'
            'table.report_aux th,table.report_aux td{border:1px solid lightgrey;'
            'padding:0 3px;text-align:left;word-wrap:break-word}'
            'table.report_aux th{background:#f0f0f0;font-weight:bold;'
            'text-align:center}'
            'table.report_aux td.amount{text-align:right;word-wrap:normal}'
            'table.report_aux tr.bold td{background:rgb(240,250,250);'
            'font-weight:bold}'
            'table.report_aux tr{page-break-inside:avoid}'
            '</style>',
            '<table class="report_aux"><thead><tr>',
        ]
        out.extend('<th>%s</th>' % escape(th[1].upper()) for th in header)
        out.append('</tr></thead><tbody>')
        for tr_data in data.get('report_data', []):
            out.append('<tr class="bold">' if tr_data.get('bold') else '<tr>')
            for k, v in tr_data.items():
                if k in skip_keys:
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    text = '{:_.2f}'.format(v).replace('.', ',').replace('_', '.')
                else:
                    text = escape(str(v)) if v else ''
                if k in amount_keys:
                    out.append('<td class="amount">%s</td>' % text)
                else:
                    out.append('<td>%s</td>' % text)
            out.append('</tr>')
        out.append('</tbody></table>')
        return ''.join(out)

    def prepare_header(self):
        report_header = [
            ('code', _('Code')),
            ('name', _('Name')),
            ('vat', 'NIT'),
            ('partner', _('Partner')),
            ('city', _('Ciudad')),
            ('date', _('Date')),
            ('journal', _('Journal')),
        ]
        if self.account_analytic:
            report_header += [
                ('analytic', _('Account Analytic')),
            ]

        report_header += [
            ('move', _('Move')),
            ('line', _('Line')),
        ]

        if self.currency_by:
            report_header += [
                ('currency', _('Currency')),
                ('amount', _('Amount')),
            ]

        report_header += [
            ('initial', _('Initial')),
            ('debit', _('Debit')),
            ('credit', _('Credit')),
            ('final', _('Final'))
        ]
        return report_header

    # VALIDAR SI SE USA
    def compute_initial_amount_by_partner(self, partner_id, account):
        domain = [
            ('partner_id', '=', partner_id),
            ('date', '<', self.date_from),
        ]
        if self.line_state:
            domain.append(('parent_state', '=', 'posted'))

        if self.report_type == 'local':
            domain.append(('account_id', '=', account.id))
        else:
            domain.append(('account_id.ifrs_account_id', '=', account.id))

        lines = self.env['account.move.line'].search(domain)
        if self.report_type == 'local':
            initial = sum(lines.mapped('debit')) - sum(lines.mapped('credit'))
        else:
            initial = sum(
                lines.mapped('ifrs_debit')
            ) - sum(
                lines.mapped('ifrs_credit')
            )
        return initial

    def group_total_amounts_for_partners(self, query_data, account):
        partner_lines = []
        partner_ids = [
            (rd.get('vat'), rd.get('partner'))
            for rd in query_data if rd.get('account_id') == account.id
        ]
        partner_ids = list(set(partner_ids))
        for partner_id in partner_ids:
            filter_lines = [
                rd for rd in query_data if rd.get('vat') == partner_id[0] and
                rd.get('account_id') == account.id
            ]
            initial_amount = self.compute_initial_amount_by_partner(
                partner_id[0], account)
            debit = sum(d.get('debit') for d in filter_lines)
            credit = sum(d.get('credit') for d in filter_lines)
            final = initial_amount + (debit - credit)
            values = {
                'bold': True,
                'group': False,
                'account_id': account.id,
                'code': account.code,
                'name': '',
                'vat': partner_id[0],
                'partner': partner_id[1],
                'date': '',
                'journal': '',
                'move': '',
                'line': 'Total: ' + partner_id[1],
            }
            if self.currency_by:
                values.update({
                    'currency': '',
                    'amount': '',
                })

            values.update({
                'initial': initial_amount,
                'debit': debit,
                'credit': credit,
                'final': final,
            })
            partner_lines.append(values)
        return partner_lines

    def prepare_data_query(self):
        query = self.prepare_query()
        self.env.cr.execute(query)
        data_query = self.env.cr.dictfetchall()
        return data_query

    def prepare_query(self):
        query = """
        select
            False as bold,
            False as group,
            aa.id as account_id,
            COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), '') as code,
            COALESCE(aa.name->'es_CO', aa.name->'en_US') as name,
            aml.partner_id as partner_id,
            rp.vat as vat,
            COALESCE(rp.name, '**') as partner,
            aml.date as date,
            aj.name as journal,
            am.name as move,
            aml.name as line,
        """

        if self.currency_by:
            query += """
                rc.name as currency,
                aml.amount_currency as amount,
            """

        query += """
            coalesce((
                select sum(aml2.debit - aml2.credit)
                from account_move_line as aml2
                where aml2.account_id = aml.account_id
                and (
                    aml2.partner_id = aml.partner_id
                    or
                    (
                        aml2.partner_id is null
                        and
                        aml.partner_id is null
                    )
                )
                and aml2.date < '{date_start}'
            ), 0) as initial,
            coalesce(aml.{debit}, 0) as debit,
            coalesce(aml.{credit}, 0) as credit,
            coalesce((
                select sum(aml2.debit - aml2.credit)
                from account_move_line as aml2
                where aml2.account_id = aml.account_id
                and (
                    aml2.partner_id = aml.partner_id
                    or
                    (
                        aml2.partner_id is null
                        and
                        aml.partner_id is null
                    )
                )
                and aml2.date <= '{date_end}'
            ), 0) as final
        from account_move_line aml
        inner join account_account aa on aa.id = aml.account_id
        inner join res_company rco on rco.id = aml.company_id
        inner join account_move am on am.id = aml.move_id
        inner join account_journal aj on aj.id = aml.journal_id
        left join res_partner rp on rp.id = aml.partner_id
        """.format(
            credit=self.report_type == 'local' and 'credit' or 'ifrs_credit',
            debit=self.report_type == 'local' and 'debit' or 'ifrs_debit',
            date_start=self.date_from,
            date_end=self.date_to
        )

        if self.currency_by:
            query += """
            left join res_currency rc on rc.id = aml.currency_id
            """

        query += """
        where aml.date between '%s' and '%s'
        """ % (
            self.date_from,
            self.date_to,
        )

        if self.line_state:
            query += """
            and aml.parent_state = 'posted'
            """

        if self.report_type == 'ifrs':
            query += """
            and aml.ifrs_type != 'local'
            """
        else:
            query += """
            and aml.ifrs_type != 'ifrs'
            """

        if self.accounts_ids:
            accounts_ids = self.accounts_ids.ids
            aids = str(tuple(accounts_ids)).replace(',)', ')')
            query += """
            and aml.account_id in %s
            """ % aids

        if self.partners_ids:
            partners_ids = self.partners_ids.ids
            pids = str(tuple(partners_ids)).replace(',)', ')')
            query += """
            and aml.partner_id in %s
            """ % pids

        query += """
        order by COALESCE(aa.code_store->>SPLIT_PART(rco.parent_path, '/', 1), ''), rp.name, aml.date
        """

        return query
