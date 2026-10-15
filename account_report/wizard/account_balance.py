# -*- coding: utf-8 -*-

import logging
from tokenize import group

from datetime import timedelta
from odoo import _, fields, models
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF'
}

_logger = logging.getLogger(__name__)


class AccountBalanceWizard(models.Model):
    _name = 'account.balance.wizard'
    _description = 'Balance Report Wizard'

    accounts_ids = fields.Many2many(comodel_name='account.account',
                                    string='Accounts')
    journal_ids = fields.Many2many(comodel_name='account.journal',
                                   string='Diarios')
    date_from = fields.Date('From',
                            default=fields.Date.today())
    date_to = fields.Date('To',
                          default=fields.Date.today())
    date_process = fields.Datetime('Fecha proceso',
                                   default=fields.Datetime.now())
    group_by = fields.Boolean('Levels?',
                              default=False,)
    line_state = fields.Boolean('Posted?',
                                default=True)
    partner_by = fields.Boolean('By partner')
    partners_ids = fields.Many2many(comodel_name='res.partner',
                                    string='Partners')
    report_type = fields.Selection(selection=[('local', 'Local'),
                                              ('ifrs', 'IFRS')],
                                   default='local',
                                   required=True)
    no_zero = fields.Boolean('Skip zero balances',
                             default=True)
    show_zero_info = fields.Boolean('Show zero info',
                                    help='Show zero balances in report',
                                    default=False)
    len_code_min = fields.Integer('Tamaño min',
                                  default=1)
    len_code_max = fields.Integer('Tamaño max',
                                  default=8)
    initial_balance = fields.Boolean('Initial balance')

    def validate_len_code(self):
        for record in self:
            if record.group_by:
                if record.len_code_min > record.len_code_max:
                    raise ValidationError(_(
                        'La longitud del código inicial '
                        'no puede ser mayor a la final'
                    ))

    def action_confirm(self):
        self.validate_len_code()
        report = self.env.ref('account_report.report_account_balance')
        data = self.prepare_data()
        return report.report_action(self, data=data)

    def button_export_pdf(self):
        self.ensure_one()
        report_type = 'qweb-pdf'
        return self._export(report_type)

    def button_export_html(self):
        self.ensure_one()
        report_type = 'qweb-html'
        return self._export(report_type)

    def _export(self, report_type='qweb-pdf'):
        self.validate_len_code()
        self.ensure_one()
        report_name = 'account_report.account_balance_qweb'
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

    def update_amounts_line(self, sum_line):
        sum_line = {
            'bold': sum_line['bold'],
            'group': sum_line['group'],
            'account_id': sum_line['account_id'],
            'parent_id': '',
            'group_id': '',
            'code': sum_line['code'],
            'name': sum_line['name'],
            'vat': '',
            'partner': '',
            'residual': sum_line['residual'],
            'debit': sum_line['debit'],
            'credit': sum_line['credit'],
            'balance': sum_line['balance'],
        }
        return sum_line

    def prepare_data(self):
        query_data = self.prepare_data_query()
        sum_line = query_data.pop()
        copy_data = list(query_data)

        # add initial balance to account with 'earnings_os_current_year'
        unaffected_earnings_account = self.env["account.account"].search(
            [
                ("account_type", "=", "equity_unaffected"),
                ("company_id", "=", self.env.companies.ids[0]),
            ], limit=1
        )
        if unaffected_earnings_account:
            unaffected_id = unaffected_earnings_account.id
            accounts_domain = [
                ("company_id", "=", self.env.companies.ids[0]),
                ("include_initial_balance", "=", False),
            ]
            accounts = self.env["account.account"].search(accounts_domain)
            aml = self.env['account.move.line']
            date_from_srt = '%s-01-01' % self.date_from.year
            domain = [
                ('date', '<', date_from_srt),
                ('company_id', '=', self.env.companies.ids[0]),
                ('account_id', 'in', accounts.ids),
            ]
            if self.line_state:
                domain.append(('parent_state', '=', 'posted'))
            if self.report_type == 'local':
                debit_read = 'debit'
                credit_read = 'credit'
                balance_read = 'balance'
                domain.append(('ifrs_type', '!=', 'ifrs'))
            else:
                debit_read = 'ifrs_debit'
                credit_read = 'ifrs_credit'
                balance_read = 'ifrs_balance'
                domain.append(('ifrs_type', '!=', 'local'))
            initial_moves = aml.read_group(
                domain=domain,
                fields=["account_id", debit_read, credit_read,
                        balance_read, "amount_currency"],
                groupby=["account_id"],
            )
            pl_initial_balance = 0.0
            for initial_balance in initial_moves:
                pl_initial_balance += initial_balance[balance_read]
            unaffected_line = list(filter(
                lambda line: line['account_id']
                == unaffected_id,
                query_data,
            ))
            if (not unaffected_line and not self.accounts_ids and not self.partners_ids and
                    not self.journal_ids):
                unaffected_line = self.create_unaffected_void_line(
                    unaffected_id)
                query_data.append(unaffected_line)
                copy_data.append(unaffected_line)
                line = unaffected_line
            else:
                if unaffected_line:
                    line = unaffected_line[0]
            if unaffected_line:
                query_data[query_data.index(
                    line)]['balance'] += pl_initial_balance
                query_data[query_data.index(
                    line)]['residual'] += pl_initial_balance
                sum_line['residual'] += pl_initial_balance
                sum_line['balance'] += pl_initial_balance

        parents = False
        if self.group_by:
            aids = [cp.get('account_id') for cp in copy_data]
            aids = list(set(aids))
            accounts = self.env['account.account'].browse(aids)
            groups = self.env['account.group'].search([])
            parents = groups
            code_groups = []
            while parents:
                for parent in parents:
                    if parent.id not in code_groups:
                        aids = parent.compute_account_ids.ids
                        datas = [
                            cp for cp in copy_data if not cp.get('bold') and
                            cp.get('account_id') in aids
                        ]
                        values = {
                            'bold': True,
                            'group': True,
                            'account_id': False,
                            'parent_id': parent.parent_id and
                            parent.parent_id.id or
                            False,
                            'group_id': parent.id,
                            'code': parent.code,
                            'name': parent.name,
                        }

                        if self.partner_by:
                            values.update({
                                'vat': '',
                                'partner': '',
                            })

                        values.update({
                            'residual': sum(d.get('residual') for d in datas),
                            'debit': sum(d.get('debit') for d in datas),
                            'credit': sum(d.get('credit') for d in datas),
                            'balance': sum(d.get('balance') for d in datas),
                        })
                        if self.no_zero and \
                            (values['residual'] != 0 or
                             values['balance'] != 0):
                            # and values['debit'] - values['credit'] != 0:
                            query_data.append(values)
                        elif not self.no_zero:
                            query_data.append(values)
                    code_groups.append(parent.id)
                parents = parents.parent_id

            if self.group_by and groups:
                query_data = sorted(
                    query_data,
                    key=lambda r: [r.get('code'), not r.get('bold')]
                )

        if self.partner_by or parents:
            sum_line = self.update_amounts_line(sum_line)

        query_data = sorted(
            query_data,
            key=lambda r: [r.get('code') or '', not r.get('bold')]
        )

        if self.group_by:
            filter_code_range = list(filter(
                lambda x: int(len(x.get('code') or '')) >= self.len_code_min and
                int(len(x.get('code') or '')) <= self.len_code_max, query_data))
            query_data = self.sum_amounts_filtered(filter_code_range)

        query_data.append(sum_line)
        return {'report_data': query_data and query_data or []}

    def create_unaffected_void_line(self, unaffected_id):
        unaffected_line = {}
        if unaffected_id:
            unaffected_account = self.env['account.account'].browse(
                unaffected_id
            )
            unaffected_line = {
                'bold': False,
                'group': False,
                'account_id': unaffected_account.id,
                'parent_id': '',
                'group_id': '',
                'code': unaffected_account.code,
                'name': unaffected_account.name,
                'residual': 0,
                'debit': 0,
                'credit': 0,
                'balance': 0,
            }
        return unaffected_line

    def prepare_data_query(self):
        query = self.prepare_query()
        self.env.cr.execute(query)
        data_query = self.env.cr.dictfetchall()
        data_query = self.sum_amounts(data_query)
        return data_query

    def sum_amounts(self, data_query):
        accounts_list = []
        for line in data_query:
            if line['account_id'] not in accounts_list:
                accounts_list.append(line['account_id'])
        residual = sum(i['residual'] for i in data_query)
        debit = sum(i['debit'] for i in data_query)
        credit = sum(i['credit'] for i in data_query)
        balance = sum(i['balance'] for i in data_query)
        sum_line = {
            'bold': True,
            'group': False,
            'account_id': '',
            'parent_id': '',
            'group_id': '',
            'code': '',
            'name': 'Total',
            'residual': residual,
            'debit': debit,
            'credit': credit,
            'balance': balance
        }
        data_query.append(sum_line)
        return data_query

    def prepare_query(self):
        query_account = self.prepare_query_account()
        query_before = self.prepare_query_before_2()
        query_after = self.prepare_query_after()

        query = """
        select
            False as bold,
            False as group,
            aml.account_id,
            '' as parent_id,
            '' as group_id,
            aml.code,
            aml.name,
        """

        if self.partner_by:
            query += """
                aml.vat,
                aml.partner,
            """

        query += """
        coalesce(amlb.debit, 0) - coalesce(amlb.credit, 0) as residual,
        coalesce(amla.debit, 0) as debit,
        coalesce(amla.credit, 0) as credit,
        (coalesce(amlb.debit, 0) - coalesce(amlb.credit, 0)) +
         (coalesce(amla.debit, 0) - coalesce(amla.credit, 0)) as balance
        from (%s) aml
        left join (%s) amlb ON
        """ % (query_account, query_before)

        if self.partner_by:
            query += """
             (
                (amlb.account_id = aml.account_id AND
                 amlb.partner_id = aml.partner_id)
                OR
                (amlb.account_id = aml.account_id AND
                 amlb.partner_id IS null AND aml.partner_id IS null)
            )
            """
        else:
            query += """
             amlb.account_id = aml.account_id
            """

        query += """
        left join (%s) amla ON
        """ % (query_after)

        if self.partner_by:
            query += """
             (
                (amla.account_id = aml.account_id AND
                 amla.partner_id = aml.partner_id)
                OR
                (amla.account_id = aml.account_id AND
                 amla.partner_id is null AND aml.partner_id is null)
            )
            """
        else:
            query += """
             amla.account_id = aml.account_id
            """
        if self.no_zero and not self.show_zero_info:
            query += """
            where coalesce(amlb.debit, 0) - coalesce(amlb.credit, 0) != 0
                or (
                    coalesce(amlb.debit, 0) - coalesce(amlb.credit, 0)
                ) + (
                    coalesce(amla.debit, 0) - coalesce(amla.credit, 0)
                ) != 0
            """
        return query

    def prepare_query_account(self):
        date = self.date_to.strftime('%Y-%m-%d')
        ids_companies = self.env.companies.ids
        ids_companies = str(tuple(ids_companies)).replace(',)', ')')

        query = """
        select 
            aa.id as account_id,
            (jsonb_each_text(aa.code_store)).value as code,
            COALESCE(aa.name->'es_CO', aa.name->'en_US') as name
        """

        if self.partner_by:
            query += """
            , aml.partner_id, rp.vat, rp.name as partner
            """

        query += """
        from account_move_line aml
        """

        query += """
            inner join account_account aa on aa.id = aml.account_id
            """
        if self.journal_ids:
            query += """
            inner join account_journal aj on aj.id = aml.journal_id
            """

        if self.partner_by:
            query += """
            left join res_partner rp on rp.id = aml.partner_id
            """

        query += """
        where aml.date <= '%s'
        and aml.company_id in %s
        """ % (date, ids_companies)

        if self.line_state:
            query += """
            and aml.parent_state = 'posted'
            """

        if self.accounts_ids:
            accounts_ids = self.accounts_ids.ids
            aids = str(tuple(accounts_ids)).replace(',)', ')')
            query += """
            and aml.account_id in %s
            """ % aids

        if self.journal_ids:
            journal_ids = self.journal_ids.ids
            jids = str(tuple(journal_ids)).replace(',)', ')')
            query += """
            and aml.journal_id in %s
            """ % jids

        if self.partner_by and self.partners_ids:
            partners_ids = self.partners_ids.ids
            pids = str(tuple(partners_ids)).replace(',)', ')')
            query += """
            and aml.partner_id in %s
            """ % pids

        query += """
        group by aa.id, aa.code_store, aa.name
        """

        if self.partner_by:
            query += """
            , aml.partner_id, rp.vat, rp.name
            """

        query += """
        order by aa.code_store
        """

        return query

    def prepare_query_before_2(self):
        if self.date_from.month == 1 and self.date_from.day == 1:
            query = self.prepare_query_before(apply_filter=True)
        else:
            select_partner = ""
            group_partner = ""
            if self.partner_by:
                select_partner = " initial_amounts.partner_id as partner_id, "
                group_partner = ", initial_amounts.partner_id"
            query = "select initial_amounts.account_id as account_id, " + select_partner + \
                " sum(initial_amounts.debit) as debit, sum(initial_amounts.credit) as credit from ("
            query = query + self.prepare_query_before(apply_filter=False)
            query = query + ' UNION ALL ' + \
                self.prepare_query_before(apply_filter=True)
            query = query + ") as initial_amounts group by initial_amounts.account_id" + \
                group_partner + " order by initial_amounts.account_id"
        return query

    def prepare_query_before(self, apply_filter):
        if apply_filter:
            date = '%s-01-01' % self.date_from.year
        else:
            date = (self.date_from - timedelta(days=1)).strftime('%Y-%m-%d')
        ids_companies = self.env.companies.ids
        ids_companies = str(tuple(ids_companies)).replace(',)', ')')

        query = """
        select aa.id as account_id,
        """

        if self.partner_by:
            query += """
            aml.partner_id as partner_id,
            """

        if self.report_type == 'ifrs':
            query += """
            sum(aml.ifrs_debit) as debit,
            sum(aml.ifrs_credit) as credit
            """
        else:
            query += """
            sum(aml.debit) as debit,
            sum(aml.credit) as credit
            """

        query += """
        from account_move_line aml
        """

        query += """
            inner join account_account aa on aa.id = aml.account_id
        """

        if not apply_filter:
            query += """
                where aml.date between '%s' and '%s'
            """ % ('%s-01-01' % self.date_from.year, date)
        else:
            query += """
            where aml.date < '%s'
            """ % date

        query += """
        and aml.company_id in %s
        """ % ids_companies

        if self.line_state:
            query += """
            and aml.parent_state = 'posted'
            """
        if self.report_type == 'ifrs':
            query += "and aml.ifrs_type != 'local'"
        else:
            query += "and aml.ifrs_type != 'ifrs'"

        if self.partner_by and self.partners_ids:
            partners_ids = self.partners_ids.ids
            pids = str(tuple(partners_ids)).replace(',)', ')')
            query += """
            and aml.partner_id in %s
            """ % pids
        if self.journal_ids:
            journal_ids = self.journal_ids.ids
            jids = str(tuple(journal_ids)).replace(',)', ')')
            query += """
            and aml.journal_id in %s
            """ % jids
        if apply_filter:
            query += """
                and aa.include_initial_balance = true
            """
        query += """
        group by aa.id
        """

        if self.partner_by:
            query += """
            , aml.partner_id
            """

        return query

    def prepare_query_after(self):
        date_from = self.date_from.strftime('%Y-%m-%d')
        date_to = self.date_to.strftime('%Y-%m-%d')
        ids_companies = self.env.companies.ids
        ids_companies = str(tuple(ids_companies)).replace(',)', ')')

        query = """
        select aa.id as account_id,
        """

        if self.partner_by:
            query += """
            aml.partner_id,
            """

        if self.report_type == 'ifrs':
            query += """
            sum(aml.ifrs_debit) as debit,
            sum(aml.ifrs_credit) as credit
            """
        else:
            query += """
            sum(aml.debit) as debit,
            sum(aml.credit) as credit
            """

        query += """
        from account_move_line aml
        """

        query += """
            inner join account_account aa on aa.id = aml.account_id
            """

        query += """
        where aml.date between '%s' and '%s'
        """ % (date_from, date_to)
        query += """
        and aml.company_id in %s
        """ % ids_companies

        if self.line_state:
            query += """
            and aml.parent_state = 'posted'
            """

        if self.report_type == 'ifrs':
            query += "and aml.ifrs_type != 'local'"
        else:
            query += "and aml.ifrs_type != 'ifrs'"

        if self.partner_by and self.partners_ids:
            partners_ids = self.partners_ids.ids
            pids = str(tuple(partners_ids)).replace(',)', ')')
            query += '''
            AND aml.partner_id in %s
            ''' % pids
        if self.journal_ids:
            journal_ids = self.journal_ids.ids
            jids = str(tuple(journal_ids)).replace(',)', ')')
            query += '''
            AND aml.journal_id in %s
            ''' % jids

        query += """
        group by aa.id
        """

        if self.partner_by:
            query += """
            , aml.partner_id
            """

        return query

    def prepare_header(self):
        report_header = [
            ('code', _('Code')),
            ('name', _('Name')),
        ]

        if self.partner_by:
            report_header += [
                ('vat', 'NIT'),
                ('partner', _('Partner'))
            ]

        report_header += [
            ('residual', _('Residual amount (balance)')),
            ('debit', _('Debit')),
            ('credit', _('Credit')),
            ('balance', _('Balance amount'))
        ]

        return report_header

    def data_report_preview(self):
        self.ensure_one()
        # Asegurar que header sea lista de tuplas (clave, etiqueta)
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

        # Generar THEAD
        th_text = ''.join(
            [f'<div class="act_as_cell">{label.upper()}</div>' for _, label in header])
        html_text = html_text.replace('th_report', th_text)

        # Generar TBODY
        tr_text = ''
        for tr_data in data.get('report_data', []):
            tr_text += '<div class="act_as_row lines">'
            bold = tr_data.get('bold', False)

            for key, _ in header:
                if key in ('group', 'account_id', 'parent_id', 'group_id'):
                    continue

                value = tr_data.get(key, '')

                # Formatear números
                if isinstance(value, (int, float)):
                    formatted_value = '{:,.2f}'.format(value).replace(
                        ',', '_').replace('.', ',').replace('_', '.')
                else:
                    formatted_value = str(value or '')

                # Determinar clases CSS
                class_span = ' '.join([
                    'bold-cell-report back-cell' if bold else 'normal-cell-report',
                    'amount' if key in (
                        'initial', 'debit', 'credit', 'final', 'balance', 'residual') else 'left'
                ])

                tr_text += f'<div class="act_as_cell {class_span}">{formatted_value}</div>'

            tr_text += '</div>'

        html_text = html_text.replace('data_report', tr_text)
        return html_text

    def sum_amounts_filtered(self, data_query):
        if not data_query:
            return data_query
        level_min = int(self.len_code_min)
        data_query_to_sum = []
        while not data_query_to_sum:
            data_query_to_sum = list(filter(
                lambda d: int(len(d.get('code'))) == level_min, data_query))
            level_min += 1
        return data_query
