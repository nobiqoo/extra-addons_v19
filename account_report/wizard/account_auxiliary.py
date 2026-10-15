# -*- coding: utf-8 -*-

import logging

from odoo import _, fields, models, api
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF'
}

_logger = logging.getLogger(__name__)


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
        data = self.prepare_data()
        return report.report_action(self, data=data)

    def button_export_pdf(self):
        self.ensure_one()
        report_type = 'qweb-pdf'
        return self._export(report_type)

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
            (jsonb_each_text(aa.code_store)).value as code,
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
                GROUP BY aml.id, aa.id, rp.vat, rp.name, aj.name, am.name, rc_line.name, rc_move.name, am.ref
                """

        query += """
        order by aa.code_store, rp.name, aml.date
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
            (jsonb_each_text(aa.code_store)).value as code,
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
            coalesce((
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
            sum(coalesce(aml.{debit}, 0)) as debit,
            sum(coalesce(aml.{credit}, 0)) as credit,
            coalesce((
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
        from account_move_line aml
        inner join account_account aa on aa.id = aml.account_id
        inner join account_move am on am.id = aml.move_id
        left join res_partner rp on rp.id = aml.partner_id
        left join res_city rc_line on rc_line.id = aml.city_id 
        left join res_city rc_move on rc_move.id = am.city_id 
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
        group by aa.code_store, aa.id, aml.partner_id, rp.vat, rp.name, rc_line.name, rc_move.name
        order by aa.code_store, rp.name
        """
        return query

    def prepare_data_acc(self):
        query = """
        select
            True as bold,
            False as group,
            aa.id as account_id,
            (jsonb_each_text(aa.code_store)).value as code,
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
            coalesce((
                select sum(aml2.{debit} - aml2.{credit})
                from account_move_line as aml2
                inner join account_move am2 on am2.id = aml2.move_id
                where aml2.account_id = aa.id
                and aml2.date < '{date_start}'
                {where2}
            ), 0) as initial,
            sum(coalesce(aml.{debit}, 0)) as debit,
            sum(coalesce(aml.{credit}, 0)) as credit,
            coalesce((
                select sum(aml2.{debit} - aml2.{credit})
                from account_move_line as aml2
                inner join account_move am2 on am2.id = aml2.move_id
                where aml2.account_id = aa.id
                and aml2.date <= '{date_end}'
                {where2}
            ), 0) as final
        from account_move_line aml
        inner join account_account aa on aa.id = aml.account_id
        inner join account_move am on am.id = aml.move_id
        left join res_city rc_line on rc_line.id = aml.city_id 
        left join res_city rc_move on rc_move.id = am.city_id 
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
        group by aa.code_store, aa.id, rc_line.name, rc_move.name
        order by aa.code_store
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
            coalesce((
                select sum(aml2.{debit} - aml2.{credit})
                from account_move_line as aml2
                inner join account_move am2 on am2.id = aml2.move_id
                where (aml2.partner_id = aml.partner_id 
                        OR
                        (aml2.partner_id is null AND aml.partner_id is null))
                    AND aml2.date < '{date_start}'
                    {where2}
            ), 0) as initial,
            sum(coalesce(aml.{debit}, 0)) as debit,
            sum(coalesce(aml.{credit}, 0)) as credit,
            coalesce((
                select sum(aml2.{debit} - aml2.{credit})
                from account_move_line as aml2
                inner join account_move am2 on am2.id = aml2.move_id
                where (aml2.partner_id = aml.partner_id
                        OR
                        (aml2.partner_id is null AND aml.partner_id is null))
                    AND aml2.date <= '{date_end}'
                    {where2}
                ), 0) as final
        from account_move_line aml
        inner join account_account aa on aa.id = aml.account_id
        inner join account_move am on am.id = aml.move_id
        left join res_partner rp on rp.id = aml.partner_id
        left join res_city rc_line on rc_line.id = aml.city_id  
        left join res_city rc_move on rc_move.id = am.city_id 
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
        group by aml.partner_id, rp.vat, rp.name, rc_line.name, rc_move.name
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
        self.ensure_one()
        header = self.prepare_header()
        data = self.prepare_data()

        report_name = _('Libro Auxiliar')
        company = self.env.company.name
        vat = self.env.company.vat
        date_from = self.date_from
        date_to = self.date_to

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

        # THEAD
        th_text = ''
        for th in header:
            th_text += '<div class="act_as_cell" style="font-size: 13px; font-family: helvetica;">%s</div>' % th[1].upper()
        html_text = html_text.replace('th_report', th_text)

        # TBODY
        tr_text = ''
        c = 1
        for tr_data in data.get('report_data', []):
            tr_text += '<div class="act_as_row lines">'
            bold = False
            for k, v in tr_data.items():
                if k == 'bold':
                    bold = v
                elif k in ('group', 'account_id'):
                    continue
                else:
                    class_span = ' '.join([
                        bold and 'bold-cell-report back-cell' \
                            or 'normal-cell-report',
                        k in ('initial', 'debit', 'credit', 'final') and 'amount' \
                            or 'left'])
                    tr_text += '<div class="act_as_cell %s" style="font-size: 13px; font-family: helvetica;">%s</div>' % (
                        class_span,
                        type(v) in (type(2), type(2.3)) \
                            and '{:_.2f}'.format(v).replace('.', ',').replace('_', '.') \
                                or v or '')
            tr_text += '</div>'
            c += 1

        html_text = html_text.replace('data_report', tr_text)
        now = fields.Datetime.context_timestamp(
            self,
            fields.Datetime.now()
        ).strftime('%d-%m-%Y %H:%M:%S')

        # HEADER
        # table_h = '''
        #     <div class="act_as_table data_table">
        #         <div class="act_as_row">
        #             <div class="act_as_cell labels" style="font-size: 13px;">{inf_tag}</div>
        #             <div class="act_as_cell" style="font-size: 13px;">{inf_val}</div>
        #             <div class="act_as_cell labels" style="font-size: 13px;">{dat_tag}</div>
        #             <div class="act_as_cell" style="font-size: 13px;">{dat_val}</div>
        #         </div>
        #         <div class="act_as_row">
        #             <div class="act_as_cell labels" style="font-size: 13px;">{com_tag}</div>
        #             <div class="act_as_cell" style="font-size: 13px;">{com_val}</div>
        #             <div class="act_as_cell labels" style="font-size: 13px;">{ini_tag}</div>
        #             <div class="act_as_cell" style="font-size: 13px;">{ini_val}</div>
        #         </div>
        #         <div class="act_as_row">
        #             <div class="act_as_cell labels" style="font-size: 13px;">{nit_tag}</div>
        #             <div class="act_as_cell" style="font-size: 13px;">{nit_val}</div>
        #             <div class="act_as_cell labels" style="font-size: 13px;">{end_tag}</div>
        #             <div class="act_as_cell" style="font-size: 13px;">{end_val}</div>
        #         </div>
        #         <div class="act_as_row">
        #             <div class="act_as_cell labels" style="font-size: 13px;">{type_tag}</div>
        #             <div class="act_as_cell" style="font-size: 13px;">{type_val}</div>
        #             <div class="act_as_cell labels" style="font-size: 13px;"></div>
        #             <div class="act_as_cell" style="font-size: 13px;"></div>
        #         </div>
        #     </div>
        # '''.format(
        #     inf_tag=_('Report'),
        #     inf_val=report_name,
        #     dat_tag=_('Date'),
        #     dat_val=now,
        #     com_tag=_('Company'),
        #     com_val=company,
        #     ini_tag=_('From'),
        #     ini_val=date_from,
        #     nit_tag=_('NIT'),
        #     nit_val=vat,
        #     end_tag=_('To'),
        #     end_val=date_to,
        #     type_tag=_('Type'),
        #     type_val=REPORT_TYPE.get(self.report_type)
        # )

        # html_text = html_text.replace('table_header', table_h)
        return html_text

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
            (jsonb_each_text(aa.code_store)).value as code,
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
        order by aa.code_store, rp.name, aml.date
        """

        return query
