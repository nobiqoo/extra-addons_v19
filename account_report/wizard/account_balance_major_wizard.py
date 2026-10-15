# -*- coding: utf-8 -*-

from odoo import _, fields, models, api
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF'
}


class AccountBalanceMajorWizard(models.Model):
    _name = 'account.balance.major.wizard'
    _description = 'Account Balance Major Wizard'

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
                              default=True,)

    line_state = fields.Boolean('Posted?',
                                default=True)
    partner_by = fields.Boolean('By partner',
                                default=True)
    partners_ids = fields.Many2many(comodel_name='res.partner',
                                    string='Partners')
    report_type = fields.Selection(selection=[('local', 'Local'),
                                              ('ifrs', 'IFRS')],
                                   default='local',
                                   required=True)
    filter_code = fields.Boolean('¿Filtrar por niveles?',
                                 default=True)
    len_code_min = fields.Integer('Tamaño min',
                                  default=1)
    len_code_max = fields.Integer('Tamaño max',
                                  default=6)
    no_zero = fields.Boolean('Skip zero balances',
                             default=True)

    def action_confirm(self):
        self.validate_len_code()
        report = self.env.ref('account_report.report_account_balance_major')
        data = self.prepare_data()
        return report.report_action(self, data=data)

    def button_export_pdf(self):
        self.ensure_one()
        self.validate_len_code()
        report_type = "qweb-pdf"
        return self._export(report_type)

    def button_preview_html(self):
        self.ensure_one()
        self.validate_len_code()
        report_type = "qweb-html"
        return self._export(report_type)

    def validate_len_code(self):
        for record in self:
            if record.filter_code:
                if record.len_code_min > record.len_code_max:
                    raise ValidationError(_(
                        'La longitud del código inicial '
                        'no puede ser mayor a la final'
                    ))

    def _export(self, report_type):
        """Default export is PDF."""
        return self._print_report(report_type)

    def _print_report(self, report_type):
        self.ensure_one()
        report_name = 'account_report.account_balance_major_qweb'
        action_report = self.env["ir.actions.report"].search(
            [
                ("report_name", "=", report_name),
                ("report_type", "=", report_type)
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
        query_data = self.prepare_data_query()
        sum_line = query_data.pop()
        copy_data = list(query_data)

        if self.partner_by:
            aids = [rd.get('account_id') for rd in copy_data]
            aids = list(set(aids))
            accounts = self.env['account.account'].browse(aids)
            for account in accounts:
                datas = [
                    rd for rd in copy_data if rd.get(
                        'account_id') == account.id
                ]
                values = {
                    'bold': True,
                    'group': False,
                    'account_id': account.id,
                    'parent_id': False,
                    'vat': '',
                    'partner': '',
                    'group_id': '',
                    'code': account.code,
                    'name': account.name,
                    'initial_debit': sum(
                        d.get('initial_debit') for d in datas),
                    'initial_credit': sum(
                        d.get('initial_credit') for d in datas),
                    'debit': sum(d.get('debit') for d in datas),
                    'credit': sum(d.get('credit') for d in datas),
                    'final_debit': sum(
                        d.get('final_debit') for d in datas),
                    'final_credit': sum(
                        d.get('final_credit') for d in datas),
                }
                query_data.append(values)

            # query_data = sorted(
            #     query_data,
            #     key=lambda r: [r.get('code_prefix_start'), r.get('partner')]
            # )
        copy_data = list(query_data)
        parents = False
        if self.group_by:
            aids = [cp.get('account_id') for cp in copy_data]
            aids = list(set(aids))
            accounts = self.env['account.account'].browse(aids)
            # groups = accounts.group_id
            groups = self.env['account.group'].search([])
            parents = groups
            code_groups = []
            # for group in groups:
            #     aids = group.account_ids.ids
            #     datas = [
            #         cp for cp in copy_data if cp.get('account_id') in aids
            #     ]
            #     values = {
            #         'bold': True,
            #         'group': True,
            #         'account_id': group.id,
            #         'vat': '',
            #         'partner': '',
            #         'parent_id': \
            #               group.parent_id and group.parent_id.id or False,
            #         'group_id': group.id,
            #         'code': group.code,
            #         'name': group.name,
            #     }

            #     values.update({
            #         #'residual': sum(d.get('residual') for d in datas),
            #         'initial_debit': sum(
            # d.get('initial_debit') for d in datas),
            #         'initial_credit': sum(
            # d.get('initial_credit') for d in datas),
            #         'debit': sum(d.get('debit') for d in datas),
            #         'credit': sum(d.get('credit') for d in datas),
            #         'final_debit': sum(
            # d.get('final_debit') for d in datas),
            #         'final_credit': sum(
            # d.get('final_credit') for d in datas),
            #         #'balance': sum(d.get('balance') for d in datas),
            #     })

            #     query_data.append(values)

            # parents = groups.parent_id
            # code_groups = groups.ids
            while parents:
                # new_data = list(query_data)
                for parent in parents:
                    if parent.id not in code_groups:
                        # cids = parent.child_ids.ids
                        aids = parent.compute_account_ids.ids
                        datas = [
                            cp for cp in copy_data if cp.get('bold') and
                            cp.get('account_id') in aids
                        ]
                        values = {
                            'bold': True,
                            'group': True,
                            'account_id': False,  # parent.id,
                            'parent_id': parent.parent_id and \
                            parent.parent_id.id or False,
                            'group_id': parent.id,
                            'vat': '',
                            'partner': '',
                            'code': parent.code,
                            'name': parent.name,
                        }

                        values.update({
                            # 'residual': sum(
                            # d.get('residual') for d in datas),
                            'initial_debit': sum(
                                d.get('initial_debit') for d in datas),
                            'initial_credit': sum(
                                d.get('initial_credit') for d in datas),
                            'debit': sum(d.get('debit') for d in datas),
                            'credit': sum(d.get('credit') for d in datas),
                            'final_debit': sum(
                                d.get('final_debit') for d in datas),
                            'final_credit': sum(
                                d.get('final_credit') for d in datas),
                            # 'balance': sum(d.get('balance') for d in datas),
                        })

                        if self.no_zero and (
                                values['initial_debit'] != 0 or
                                values['initial_credit'] != 0 or
                                values['debit'] != 0 or
                                values['credit'] != 0 or
                                values['final_debit'] != 0 or
                                values['final_credit'] != 0):
                            query_data.append(values)
                        elif not self.no_zero:
                            query_data.append(values)
                        code_groups.append(parent.id)
                parents = parents.parent_id

            if self.group_by and groups:
                query_data = sorted(
                    query_data,
                    key=lambda r: [r.get('code') or '', not r.get('bold')])

        # ids_group_parent = list(filter(
        # lambda q: q.get('parent_id') == False, query_data))
        # if ids_group_parent:
        #     ids_group_parent = sorted(
        #             ids_group_parent,
        #             key=lambda r: r.get('code')
        #         )

        # index = 0
        # index2 = 0
        # for parent in ids_group_parent:
        #     if parent.get('group_id'):
        #         parents2 = list(filter(
        #             lambda x: x.get('parent_id') == parent.get('group_id'),
        #             query_data
        #         ))
        #         parents2 = sorted(
        #             parents2,
        #             key=lambda x: x.get('code')
        #         )
        #         index2 = index
        #         for parent2 in parents2:
        #             if not self.partner_by:
        #                 c_ident = parent.get('code').count('| ') + 1
        #                 parent2['code'] = '| '*c_ident + parent2.get('code')
        #                 index2 += 1
        #                 ids_group_parent.insert(index2, parent2)
        #     index += 1

        if self.partner_by or parents:
            sum_line = self.update_amounts_line(sum_line)

        query_data.append(sum_line)

        if self.filter_code:
            filter_group = list(
                filter(lambda x: x.get('bold') is True, query_data))
            filter_code_range = list(filter(
                lambda x: int(len(x.get('code') or '')) >= self.len_code_min and
                int(len(x.get('code') or '')) <= self.len_code_max, filter_group))
            query_data = self.sum_amounts_filtered(filter_code_range)

        return {'report_data': query_data and query_data or []}

    def prepare_data_query(self):
        query = self.prepare_query()
        self.env.cr.execute(query)
        data_query = self.env.cr.dictfetchall()
        data_query = self.sum_amounts(data_query)
        return data_query

    def prepare_query(self):
        query_account = self.prepare_query_account()
        query_before = self.prepare_query_before()
        query_after = self.prepare_query_after()

        query = """
        select 
            False as bold,
            False as group,
            aml.vat,
            aml.partner,
            aml.account_id,
            '' as parent_id,
            '' as group_id,
            -- aml.code,
            aml.name,
        """
        query += """
        coalesce(amlb.debit, 0) as initial_debit,
        coalesce(amlb.credit, 0) as initial_credit,
        coalesce(amla.debit, 0) as debit,
        coalesce(amla.credit, 0) as credit,
        coalesce(amlb.debit, 0) + coalesce(amla.debit, 0) as final_debit,
        coalesce(amlb.credit, 0) + coalesce(amla.credit, 0) as final_credit
        from (%s) aml
        left join account_account aa on aml.account_id = aa.id
        left join (%s) amlb on
        """ % (query_account, query_before)

        if self.partner_by:
            query += """
             (
                (amlb.account_id = aml.account_id AND
                 amlb.partner_id = aml.partner_id)
                OR
                (amlb.account_id = aml.account_id AND
                 amlb.partner_id is null AND aml.partner_id is null)
            )
            """
        else:
            query += """
             amlb.account_id = aml.account_id
            """
        query += """
        left join (%s) amla on
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
        if self.no_zero:
            query += """
            where coalesce(amlb.debit, 0) != 0  
                or coalesce(amlb.credit, 0) != 0
                or coalesce(amla.debit, 0) != 0
                or coalesce(amla.credit, 0) != 0
                or coalesce(amlb.debit, 0) + coalesce(amla.debit, 0) != 0
                or coalesce(amlb.credit, 0) + coalesce(amla.credit, 0) != 0
            """
            # where coalesce(amlb.debit, 0) - coalesce(amlb.credit, 0) != 0
            #     or (
            #         coalesce(amlb.debit, 0) - coalesce(amlb.credit, 0)
            #     ) + (
            #         coalesce(amla.debit, 0) - coalesce(amla.credit, 0)
            #     ) != 0
            # """
        return query

    def prepare_query_account(self):
        date = self.date_to.strftime('%Y-%m-%d')
        ids_companies = self.env.companies.ids
        ids_companies = str(tuple(ids_companies)).replace(',)', ')')
        query = """
        select aa.id as account_id, aa.code_store, aa.name
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
            query += '''
            AND aml.journal_id in %s
            ''' % jids
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

    def prepare_query_before(self):
        date = self.date_from.strftime('%Y-%m-%d')
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

        if self.journal_ids:
            journal_ids = self.journal_ids.ids
            jids = str(tuple(journal_ids)).replace(',)', ')')
            query += """
            and aml.journal_id in %s
            """ % jids
        
        query += """
        group by aa.id
        """

        if self.partner_by:
            query += """
            , aml.partner_id
            """
        return query

    def sum_amounts(self, data_query):
        debit = sum(i['debit'] for i in data_query)
        credit = sum(i['credit'] for i in data_query)
        initial_debit = sum(i['initial_debit'] for i in data_query)
        initial_credit = sum(i['initial_credit'] for i in data_query)
        final_debit = sum(i['final_debit'] for i in data_query)
        final_credit = sum(i['final_credit'] for i in data_query)
        # balance = sum(i['balance'] for i in data_query)
        sum_line = {
            'bold': True,
            'group': False,
            'vat': '',
            'partner': '',
            'account_id': '',
            'parent_id': '',
            'group_id': '',
            'code': '',
            'name': 'TOTAL',
            'initial_debit': initial_debit,
            'initial_credit': initial_credit,
            'debit': debit,
            'credit': credit,
            'final_debit': final_debit,
            'final_credit': final_credit,
        }
        data_query.append(sum_line)
        return data_query

    def sum_amounts_filtered(self, data_query):
        level_min = int(self.len_code_min)
        data_query_to_sum = []
        while not data_query_to_sum:
            data_query_to_sum = list(filter(
                lambda d: int(len(d.get('code'))) == level_min, data_query))
            level_min += 1
        debit = sum(i['debit'] for i in data_query_to_sum)
        credit = sum(i['credit'] for i in data_query_to_sum)
        initial_debit = sum(i['initial_debit'] for i in data_query_to_sum)
        initial_credit = sum(i['initial_credit'] for i in data_query_to_sum)
        final_debit = sum(i['final_debit'] for i in data_query_to_sum)
        final_credit = sum(i['final_credit'] for i in data_query_to_sum)
        sum_line = {
            'bold': True,
            'group': False,
            'vat': '',
            'partner': '',
            'account_id': '',
            'parent_id': '',
            'group_id': '',
            'code': '',
            'name': 'TOTAL',
            'initial_debit': initial_debit,
            'initial_credit': initial_credit,
            'debit': debit,
            'credit': credit,
            'final_debit': final_debit,
            'final_credit': final_credit,
        }
        data_query.append(sum_line)
        return data_query

    def update_amounts_line(self, sum_line):
        sum_line_data = {
            'bold': sum_line['bold'],
            'group': sum_line['group'],
            'account_id': sum_line['account_id'],
            'parent_id': '',
            'group_id': '',
            'vat': '',
            'partner': '',
            'code': sum_line['code'],
            'name': sum_line['name'],
            'initial_debit': sum_line['initial_debit'],
            'initial_credit': sum_line['initial_credit'],
            'debit': sum_line['debit'],
            'credit': sum_line['credit'],
            'final_debit': sum_line['final_debit'],
            'final_credit': sum_line['final_credit'],
        }
        return sum_line_data

    def data_report_preview(self):
        self.ensure_one()
        header = self.prepare_header()
        data = self.prepare_data()

        # report_name = _('Libro Mayor y balance')
        # company = self.env.company.name
        # vat = self.env.company.vat
        # date_from = self.date_from
        # date_to = self.date_to

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
            th_text += '<div class="act_as_cell">%s</div>' % th[1].upper()
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
                elif k in ('group', 'account_id', 'parent_id',
                           'vat', 'partner', 'group_id'):
                    continue
                else:
                    class_span = ' '.join([
                        bold and 'bold-cell-report back-cell' \
                            or 'normal-cell-report',
                        k in ('initial', 'debit', 'credit', 'final',
                              'initial_debit', 'initial_credit',
                              'final_debit', 'final_credit') and 'amount' \
                            or 'left'])
                    tr_text += '<div class="act_as_cell %s">%s</div>' % (
                        class_span,
                        type(v) in (type(2), type(2.3))
                        and '{:_.2f}'.format(v).replace('.', ',').replace('_', '.')
                        or v or '')
            tr_text += '</div>'
            c += 1

        html_text = html_text.replace('data_report', tr_text)
        # now = fields.Datetime.context_timestamp(
        #     self,
        #     fields.Datetime.now()
        # ).strftime('%d-%m-%Y %H:%M:%S')

        # HEADER
        # table_h = '''
        #     <div class="act_as_table data_table">
        #         <div class="act_as_row">
        #             <div class="act_as_cell labels">{inf_tag}</div>
        #             <div class="act_as_cell">{inf_val}</div>
        #             <div class="act_as_cell labels">{dat_tag}</div>
        #             <div class="act_as_cell">{dat_val}</div>
        #         </div>
        #         <div class="act_as_row">
        #             <div class="act_as_cell labels">{com_tag}</div>
        #             <div class="act_as_cell">{com_val}</div>
        #             <div class="act_as_cell labels">{ini_tag}</div>
        #             <div class="act_as_cell">{ini_val}</div>
        #         </div>
        #         <div class="act_as_row">
        #             <div class="act_as_cell labels">{nit_tag}</div>
        #             <div class="act_as_cell">{nit_val}</div>
        #             <div class="act_as_cell labels">{end_tag}</div>
        #             <div class="act_as_cell">{end_val}</div>
        #         </div>
        #         <div class="act_as_row">
        #             <div class="act_as_cell labels">{type_tag}</div>
        #             <div class="act_as_cell">{type_val}</div>
        #             <div class="act_as_cell labels"></div>
        #             <div class="act_as_cell"></div>
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
            ('initial_debit', _('Inicial débito')),
            ('initial_credit', _('Inicial crédito')),
            ('debit', _('Débito')),
            ('credit', _('Crédito')),
            ('final_debit', _('Final Débito')),
            ('final_credit', _('Final Crédito'))
        ]
        return report_header

    def td_format(self, v):
        return type(v) in (type(2), type(2.3)) and \
            '{:_.2f}'.format(v).replace('.', ',').replace('_', '.') or \
            v or ''
