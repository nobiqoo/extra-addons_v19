# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF'
}


class AccountauxiliaryInvoicesWizard(models.Model):
    _name = 'account.auxiliary.invoices.wizard'
    _description = 'Auxiliary Report Invoices Wizard'

    accounts_ids = fields.Many2many(comodel_name='account.account',
                                    string='Accounts')
    currency_by = fields.Boolean('Multi-currency?',
                                 default=False,)
    date_from = fields.Date('From',
                            default=fields.Date.today())
    date_to = fields.Date('To',
                          default=fields.Date.today())
    line_state = fields.Boolean('Posted?',
                                default=True)
    partner_by = fields.Boolean('By partner')
    partners_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Partners')
    report_type = fields.Selection(selection=[('local', 'Local'),
                                              ('ifrs', 'IFRS')],
                                   default='local',
                                   required=True)
    no_zero = fields.Boolean('Skip zero balances',
                             default=True)

    def action_confirm(self):
        report = self.env.ref(
            'account_report.report_account_auxiliary_invoices')
        data = self.prepare_data()
        return report.report_action(self, data=data)

    def prepare_data(self):
        Line = self.env['account.move.line']

        query_data = self.prepare_data_query()
        query_data = sorted(
            query_data,
            key=lambda r: [r.get('code'), r.get('partner'),
                           r.get('date'), r.get('move')]
        )

        return {'report_data': query_data and query_data or []}

    def prepare_data_query(self):
        query = self.prepare_query()
        self.env.cr.execute(query)
        data_query = self.env.cr.dictfetchall()
        return data_query

    def prepare_query(self):
        ids_companies = self.env.companies.ids
        ids_companies = str(tuple(ids_companies)).replace(',)', ')')
        company_id = str(self.env.company.id)

        query = """
        select
            False as bold,
            False as group,
            aa.id as account_id,
            (jsonb_each_text(code_store)).value as code,
            COALESCE(aa.name->'es_CO', aa.name->'en_US') as name,
            rp.vat as vat,
            coalesce(rp.name, '**') as partner,
            case when is_company then 'JURIDICA' else 'NATURAL' end as company_type,
            aml.date as date,
            COALESCE(aj.name->'es_CO', aa.name->'en_US') as journal,
            am.name as move,
            aml.name as line,
        """

        if self.currency_by:
            query += """
                rc.name as currency,
                aml.amount_currency as amount,
            """

        if self.report_type == 'local':
            query += """
                CASE
                WHEN (aml.tax_base_amount > 0) THEN aml.name
                ELSE ''
                END as tax_label,
                aml.tax_base_amount as base,
                aml.debit as debit,
                aml.credit as credit,
                aml.debit - aml.credit as final
            from account_move_line aml
            inner join account_account aa on aa.id = aml.account_id
            """
        else:
            query += """
                CASE
                WHEN (aml.tax_base_amount > 0) THEN aml.name
                ELSE ''
                END as tax_label,
                aml.tax_base_amount as base,
                aml.ifrs_debit as debit,
                aml.ifrs_credit as credit,
                aml.ifrs_debit - aml.ifrs_credit as final
            from account_move_line aml
            inner join account_account aa on aa.id = aml.account_id
            """

        query += """
        inner join account_move am on am.id = aml.move_id
        inner join account_journal aj on aj.id = aml.journal_id
        left join res_partner rp on rp.id = aml.partner_id
        """

        if self.currency_by:
            query += """
            left join res_currency rc on rc.id = aml.currency_id
            """

        query += """
        where aml.date between '%s' and '%s'
            and aml.company_id in %s
        """ % (
            self.date_from,
            self.date_to,
            ids_companies
        )
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

        if self.partners_ids:
            partners_ids = self.partners_ids.ids
            pids = str(tuple(partners_ids)).replace(',)', ')')
            query += """
                and aml.partner_id in %s
            """ % pids

        if self.no_zero:
            query += """
                and coalesce(aml.debit, 0) - coalesce(aml.credit, 0) != 0
            """

        query += """
        order by aa.code_store, aml.date, rp.name
        """

        return query

    def prepare_header(self):
        report_header = [
            ('code', _('Code')),
            ('name', _('Name')),
            ('vat', 'NIT'),
            ('partner', _('Partner')),
            ('company_type', _('Company Type')),
            ('date', _('Date')),
            ('journal', _('Journal')),
            ('move', _('Move')),
            ('line', _('Line')),
        ]

        if self.currency_by:
            report_header += [
                ('currency', _('Currency')),
                ('amount', _('Amount')),
            ]

        report_header += [
            ('tax_label', _('Label')),
            ('base', _('Base')),
            ('debit', _('Debit')),
            ('credit', _('Credit')),
            ('final', _('Final'))
        ]

        return report_header
