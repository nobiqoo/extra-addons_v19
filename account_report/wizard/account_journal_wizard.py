# -*- coding: utf-8 -*-

from odoo import _, fields, models, api
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF'
}


class AccountJournalWizard(models.Model):
    _name = 'account.journal.wizard'
    _description = 'Account Jornal Wizard'

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
    # group_by = fields.Boolean('Levels?',
    #                           default=False,)
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
    no_zero = fields.Boolean('Skip zero balances',
                             default=True)
    group_by_move = fields.Boolean('Por comprobante',
                                   default=False)
    filter_code = fields.Boolean('¿Filtrar por niveles?',
                                 default=False)
    len_code_min = fields.Integer('Tamaño min',
                                  default=1)
    len_code_max = fields.Integer('Tamaño max',
                                  default=6)

    @api.onchange('filter_code')
    def _onchange_filter_code(self):
        if self.filter_code:
            self.group_by_move = False

    @api.onchange('group_by_move')
    def _onchange_group_by_move(self):
        if self.group_by_move:
            self.filter_code = False

    def action_confirm(self):
        self.validate_len_code()
        report = self.env.ref('account_report.report_account_journal')
        data = self.prepare_data()
        return report.report_action(self, data=data)

    def button_export_pdf(self):
        self.ensure_one()
        self.validate_len_code()
        report_type = 'qweb-pdf'
        return self._export(report_type)

    def button_preview_html(self):
        self.ensure_one()
        self.validate_len_code()
        report_type = 'qweb-html'
        return self._export(report_type)

    def validate_len_code(self):
        for record in self:
            if record.filter_code:
                if record.len_code_min > record.len_code_max:
                    raise ValidationError(_(
                        'La longitud del código inicial '
                        'no puede ser mayor a la final'
                    ))

    def _export(self, report_type='qweb-pdf'):
        '''Default export is PDF.'''
        self.ensure_one()
        report_name = 'account_report.account_journal_qweb'
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
        query_data = self.prepare_data_query()
        sum_line = query_data.pop()
        copy_data = list(query_data)

        parents = False
        # AQUI INICIA LA AGRUPACIÓN
        if self.filter_code:
            aids = [cp.get('account_id') for cp in copy_data]
            aids = list(set(aids))
            accounts = self.env['account.account'].browse(aids)
            groups = accounts.group_id
            for group in groups:
                aids = group.account_ids.ids
                datas = [
                    cp for cp in copy_data if cp.get('account_id') in aids
                ]
                values = {
                    'bold': True,
                    'group': True,
                    'parent_id': group.parent_id \
                        and group.parent_id.id or False,
                    'group_id': group.id,
                    'journal_id': '',
                    'move_id': '',
                    'account_id': group.id,
                    'date': '',
                    'journal_name': '',
                    'move_name': '',
                    'account_code': group.code,
                    'account_name': group.name,
                    'parent_state': '',
                    'debit': sum(d.get('debit') for d in datas),
                    'credit': sum(d.get('credit') for d in datas),
                }
                query_data.append(values)

            parents = groups.parent_id
            code_groups = [] # groups.ids
            while parents:
                new_data = list(query_data)
                for parent in parents:
                    if parent.id not in code_groups:
                        cids = parent.child_ids.ids
                        datas = [
                            nd for nd in new_data if nd.get('group') and
                            nd.get('account_id') in cids
                        ]
                        values = {
                            'bold': True,
                            'group': True,
                            'parent_id': parent.parent_id \
                                and parent.parent_id.id or False,
                            'group_id': parent.id,
                            'journal_id': '',
                            'move_id': '',
                            'account_id': parent.id,
                            'date': '',
                            'journal_name': '',
                            'move_name': '',
                            'account_code': parent.code,
                            'account_name': parent.name,
                            'parent_state': '',
                            'debit': sum(d.get('debit') for d in datas),
                            'credit': sum(d.get('credit') for d in datas),
                        }
                        query_data = self._add_group_validated(
                            query_data, values)
                        # query_data.append(values)
                        # code_groups.append(parent.id)
                parents = parents.parent_id

            if self.filter_code and groups:
                query_data = sorted(query_data,
                                    key=lambda r: r.get('account_code'))
        if self.filter_code:
            filter_group = list(
                filter(lambda x: x.get('bold') is True, query_data))
            filter_code_range = list(filter(
                lambda x: int(len(x.get('account_code'))) >= self.len_code_min and
                int(len(x.get('account_code'))) <= self.len_code_max, filter_group))
            query_data = filter_code_range
            sum_line = self.sum_amounts_filtered(filter_code_range)
        elif self.group_by_move:
            moves = set([x.get('move_name') for x in copy_data])
            for move in moves:
                datas = [nd for nd in copy_data if nd.get('move_name') == move]
                values = {
                    'bold': True,
                    'group': True,
                    'parent_id': '',
                    'group_id': '',
                    'journal_id': '',
                    'move_id': '',
                    'account_id': '',
                    'date': datas[0].get('date'),
                    'journal_name': '',
                    'move_name': move,
                    'account_code': '',
                    'account_name': '',
                    'parent_state': '',
                    'debit': sum(d.get('debit') for d in datas),
                    'credit': sum(d.get('credit') for d in datas),
                }
                query_data.append(values)
            query_data = sorted(query_data,
                                key=lambda r: (r.get('date'),
                                               r.get('move_name'),
                                               r.get('bold')))
            sum_line = self.sum_amounts(list(filter(
                lambda x: x.get('bold') and not x.get('account_name'),
                query_data)))
        query_data.append(sum_line)

        # IDENTAR CODUGOS DE CUENTA
        # ids_group_parent = list(filter(lambda q: q.get('parent_id') is False,
        #                                query_data))
        # if ids_group_parent:
        #     ids_group_parent = sorted(ids_group_parent,
        #                               key=lambda r: r.get('code'))

        # index = 0
        # index2 = 0
        # for parent in ids_group_parent:
        #     if parent.get('group_id'):
        #         parents2 = list(filter(
        #             lambda x: x.get('parent_id') == parent.get('group_id'),
        #             query_data))
        #         parents2 = sorted(parents2,
        #                           key=lambda x: x.get('code'))
        #         index2 = index
        #         for parent2 in parents2:
        #             if not self.partner_by:
        #                 c_ident = parent.get('code').count('| ') + 1
        #                 parent2['code'] = '| '*c_ident + parent2.get('code')
        #                 index2 += 1
        #                 ids_group_parent.insert(index2, parent2)
        #     index += 1

        return {'report_data': query_data and query_data or []}

    def prepare_data_query(self):
        query = self.prepare_query()
        self.env.cr.execute(query)
        data_query = self.env.cr.dictfetchall()

        # aa.code_store (company_dependent) se almacena como jsonb
        # ({'<company_id>': 'texto'}); hay que extraer el valor de texto
        # plano para la compañía activa.
        for row in data_query:
            row['account_code'] = self._extract_jsonb_value(row.get('account_code'))

        sum_line = self.sum_amounts(data_query)
        data_query.append(sum_line)
        return data_query

    def _extract_jsonb_value(self, value):
        '''Si el driver nos entrega un dict (campo company_dependent),
        extraemos el valor de la compañía activa, cayendo al primer valor
        disponible.'''
        if isinstance(value, dict):
            company_id = str(self.env.company.id)
            return value.get(company_id) or next(iter(value.values()), '')
        return value or ''

    def prepare_query(self):
        date_from = self.date_from.strftime('%Y-%m-%d')
        date_to = self.date_to.strftime('%Y-%m-%d')
        ids_companies = self.env.companies.ids
        ids_companies = str(tuple(ids_companies)).replace(',)', ')')

        query = """
        select
            False as bold,
            False as group,
            '' as parent_id,
            '' as group_id,
            aml.journal_id,
            aml.move_id,
            aml.account_id,
            TO_CHAR(aml.date, 'YYYY/MM/DD') AS date,
            COALESCE(aj.name->'es_CO', aj.name->'en_US') as journal_name,
            am.name as move_name,
            aa.code_store as account_code,
            COALESCE(aa.name->'es_CO', aa.name->'en_US') as account_name,
            case when aml.parent_state = 'posted'
             then 'Publicado' else aml.parent_state end as parent_state,
        """

        if self.report_type == 'ifrs':
            query += """
                aml.ifrs_debit as debit,
                aml.ifrs_credit as credit
            """
        else:
            query += """
                aml.debit as debit,
                aml.credit as credit
            """

        query += """
        from account_move_line aml
        """

        query += """
            inner join account_account aa on aa.id = aml.account_id
            inner join account_move am on am.id = aml.move_id
            inner join account_journal aj on aj.id = aml.journal_id
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
            AND aml.journal_id in %s
            """ % jids
        
        if self.no_zero:
            query += """
                and coalesce(aml.{debit}, 0) - coalesce(aml.{credit}, 0) != 0
            """.format(
                debit=self.report_type == 'ifrs' and 'ifrs_debit' or 'debit',
                credit=self.report_type == 'ifrs' and 'ifrs_credit' or 'credit'
            )

        query += """
        order by aml.date,aml.journal_id, aj.id,aml.move_id
        """
        return query

    def sum_amounts(self, data_query):
        debit = sum(i['debit'] for i in data_query)
        credit = sum(i['credit'] for i in data_query)
        sum_line = {
            'bold': True,
            'group': False,
            'parent_id': '',
            'group_id': '',
            'journal_id': '',
            'move_id': '',
            'account_id': '',
            'date': '',
            'journal_name': '',
            'move_name': '',
            'account_code': '',
            'account_name': 'TOTAL',
            'parent_state': '',
            'debit': debit,
            'credit': credit,
        }
        return sum_line

    def _add_group_validated(self, data, value):
        code = value.get('account_code')
        in_data = list(filter(lambda x: x.get('account_code') == code, data))
        if in_data:
            data.remove(in_data[0])
        data.append(value)
        return data

    def sum_amounts_filtered(self, data_query):
        level_min = int(self.len_code_min)
        data_query_to_sum = []
        while not data_query_to_sum:
            data_query_to_sum = list(filter(
                lambda d: int(len(d.get('account_code'))) == level_min, data_query))
            level_min += 1
        sum_line = self.sum_amounts(data_query_to_sum)
        return sum_line

    def data_report_preview(self):
        self.ensure_one()
        header = self.prepare_header()
        data = self.prepare_data()

        report_name = _('Libro oficial diario')
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
                elif k in ('bold', 'group', 'journal_id',
                           'account_id', 'move_id', 'parent_id', 'group_id'):
                    continue
                else:
                    class_span = ' '.join([
                        bold and 'bold-cell-report back-cell' \
                            or 'normal-cell-report',
                        k in ('debit', 'credit') and 'amount' \
                            or 'left'])
                    tr_text += '<div class="act_as_cell %s">%s</div>' % (
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
        table_h = '''
            <div class="act_as_table data_table">
                <div class="act_as_row">
                    <div class="act_as_cell labels">{inf_tag}</div>
                    <div class="act_as_cell">{inf_val}</div>
                    <div class="act_as_cell labels">{dat_tag}</div>
                    <div class="act_as_cell">{dat_val}</div>
                </div>
                <div class="act_as_row">
                    <div class="act_as_cell labels">{com_tag}</div>
                    <div class="act_as_cell">{com_val}</div>
                    <div class="act_as_cell labels">{ini_tag}</div>
                    <div class="act_as_cell">{ini_val}</div>
                </div>
                <div class="act_as_row">
                    <div class="act_as_cell labels">{nit_tag}</div>
                    <div class="act_as_cell">{nit_val}</div>
                    <div class="act_as_cell labels">{end_tag}</div>
                    <div class="act_as_cell">{end_val}</div>
                </div>
                <div class="act_as_row">
                    <div class="act_as_cell labels">{type_tag}</div>
                    <div class="act_as_cell">{type_val}</div>
                    <div class="act_as_cell labels"></div>
                    <div class="act_as_cell"></div>
                </div>
            </div>
        '''.format(
            inf_tag=_('Report'),
            inf_val=report_name,
            dat_tag=_('Date'),
            dat_val=now,
            com_tag=_('Company'),
            com_val=company,
            ini_tag=_('From'),
            ini_val=date_from,
            nit_tag=_('NIT'),
            nit_val=vat,
            end_tag=_('To'),
            end_val=date_to,
            type_tag=_('Type'),
            type_val=REPORT_TYPE.get(self.report_type)
        )

        # html_text = html_text.replace('table_header', table_h)
        return html_text

    def prepare_header(self):
        report_header = [
            ('date', _('Fecha')),
            ('journal_name', _('Diario')),
            ('move_name', _('Comprobante')),
            ('account_code', _('Cuenta')),
            ('account_name', _('Nombre')),
            ('parent_state', _('Estado')),
            ('debit', _('Débito')),
            ('credit', _('Crédito')),
        ]
        return report_header

    def td_format(self, v):
        return type(v) in (type(2), type(2.3)) and \
            '{:_.2f}'.format(v).replace('.', ',').replace('_', '.') or \
            v or ''
