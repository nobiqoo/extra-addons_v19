# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError
from odoo.fields import Domain
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _cron_execute_followup_company(self, batch_size=1000):

        company = self.env.company

        partners = self.env['res.partner']

        followup_data = self._query_followup_data(
            all_partners=True
        )

        allowed_accounts = (
            company.followup_account_ids.ids
        )

        excluded_journals = (
            company.followup_excluded_journal_ids.ids
        )

        for values in followup_data.values():

            if (
                values.get(
                    'followup_status'
                )
                != 'in_need_of_action'
            ):
                continue

            partner = self.browse(
                values['partner_id']
            )

            domain = [

                (
                    'partner_id',
                    '=',
                    partner.id
                ),

                (
                    'company_id',
                    '=',
                    company.id
                ),

                (
                    'parent_state',
                    '=',
                    'posted'
                ),

                # ONLY CUSTOMER INVOICES
                (
                    'move_id.move_type',
                    'in',
                    [
                        'out_invoice',
                        'out_refund'
                    ]
                ),

                # Pending
                (
                    'amount_residual_currency',
                    '>',
                    0
                ),

                # Configured accounts
                (
                    'account_id',
                    'in',
                    allowed_accounts
                ),
            ]

            if excluded_journals:
                domain.append(
                    (
                        'move_id.journal_id',
                        'not in',
                        excluded_journals
                    )
                )

            aml = self.env[
                'account.move.line'
            ].search(
                domain,
                limit=1
            )

            if not aml:
                continue

            partners |= partner

        for partner in partners[:batch_size]:

            try:

                partner._execute_followup_partner()

            except UserError as e:

                partner._message_log(
                    body=str(e)
                )

                _logger.warning(
                    str(e),
                    exc_info=True
                )

        return bool(
            not partners[batch_size:]
        )

    def _get_unreconciled_aml_domain(self):
        domain = super()._get_unreconciled_aml_domain()

        company = self.env.company

        if company.followup_policy:

            if company.followup_account_ids:
                domain &= Domain(
                    'account_id',
                    'in',
                    company.followup_account_ids.ids,
                )

            if company.followup_excluded_journal_ids:
                domain &= Domain(
                    'journal_id',
                    'not in',
                    company.followup_excluded_journal_ids.ids,
                )

        return domain

    def _get_followup_report_lines(self, options):
        """
        Compute and return the lines of the columns of the follow-ups report.
        """
        # Get date format for the lang
        partner = options.get('partner_id') and self.env['res.partner'].browse(options['partner_id']) or False
        if not partner:
            return []

        lang_code = partner.lang
        lines = []
        res = {}
        today = fields.Date.today()
        line_num = 0
        aml_lines = partner.unreconciled_aml_ids

        company = self.env.company
        
        if company.followup_policy:
        
            if company.followup_account_ids:
                aml_lines = aml_lines.filtered(
                    lambda l: l.account_id in company.followup_account_ids
                )
        
            if company.followup_excluded_journal_ids:
                aml_lines = aml_lines.filtered(
                    lambda l: l.journal_id not in company.followup_excluded_journal_ids
                )
        
        for l in aml_lines.sorted().filtered(
            lambda aml: not aml.currency_id.is_zero(aml.amount_residual_currency)
        ):
            if l.company_id in self.env.company.search([('id', 'child_of', self.env.context.get('allowed_company_ids', self.env.company.id))]) and not l.blocked:
                currency = l.currency_id or l.company_id.currency_id
                if currency not in res:
                    res[currency] = []
                res[currency].append(l)
        for currency, aml_recs in res.items():
            total = 0
            total_issued = 0
            for aml in aml_recs:
                amount = aml.amount_residual_currency if aml.currency_id else aml.amount_residual
                invoice_date = {
                    'name': format_date(self.env, aml.move_id.invoice_date or aml.date, lang_code=lang_code),
                    'class': 'date',
                    'style': 'white-space:nowrap;text-align:left;',
                    'template': 'account_followup.line_template',
                }
                date_due = format_date(self.env, aml.date_maturity, lang_code=lang_code)
                total += not aml.blocked and amount or 0
                is_overdue = today > aml.date_maturity if aml.date_maturity else False
                is_payment = aml.payment_id
                if is_overdue or is_payment:
                    total_issued += not aml.blocked and amount or 0
                date_due = {
                    'name': date_due, 'class': 'date',
                    'style': 'white-space:nowrap;text-align:left;',
                    'template': 'account_followup.line_template',
                }
                if is_overdue:
                    date_due['style'] += 'color: red;'
                if is_payment:
                    date_due = ''
                move_line_name = {
                    'name': self._followup_report_format_aml_name(aml.name, aml.move_id.ref),
                    'style': 'text-align:left; white-space:normal;',
                    'template': 'account_followup.line_template',
                }
                amount = {
                    'name': formatLang(self.env, amount, currency_obj=currency),
                    'style': 'text-align:right; white-space:normal;',
                    'template': 'account_followup.line_template',
                }
                line_num += 1
                invoice_origin = aml.move_id.invoice_origin or ''
                if len(invoice_origin) > 43:
                    invoice_origin = invoice_origin[:40] + '...'
                invoice_origin = {
                    'name': invoice_origin,
                    'style': 'text-align:center; white-space:normal;',
                    'template': 'account_followup.line_template',
                }
                columns = [
                    invoice_date,
                    date_due,
                    invoice_origin,
                    move_line_name,
                    amount,
                ]
                lines.append({
                    'id': aml.id,
                    'account_move': aml.move_id,
                    'name': aml.move_id.name,
                    'move_id': aml.move_id.id,
                    'type': is_payment and 'payment' or 'unreconciled_aml',
                    'unfoldable': False,
                    'columns': [isinstance(v, dict) and v or {'name': v, 'template': 'account_followup.line_template'} for v in columns],
                })
            total_due = formatLang(self.env, total, currency_obj=currency)
            line_num += 1

            cols = \
                [{
                    'name': v,
                    'template': 'account_followup.line_template',
                } for v in [''] * 3] + \
                [{
                    'name': v,
                    'style': 'text-align:right; white-space:normal; font-weight: bold;',
                    'template': 'account_followup.line_template',
                } for v in [total >= 0 and _('Total Due') or '', total_due]]

            lines.append({
                'id': line_num,
                'name': '',
                'class': 'total',
                'style': 'border-top-style: double',
                'unfoldable': False,
                'level': 3,
                'columns': cols,
            })
            if total_issued > 0:
                total_issued = formatLang(self.env, total_issued, currency_obj=currency)
                line_num += 1

                cols = \
                    [{
                        'name': v,
                        'template': 'account_followup.line_template',
                    } for v in [''] * 3] + \
                    [{
                        'name': v,
                        'style': 'text-align:right; white-space:normal; font-weight: bold;',
                        'template': 'account_followup.line_template',
                    } for v in [_('Total Overdue'), total_issued]]

                lines.append({
                    'id': line_num,
                    'name': '',
                    'class': 'total',
                    'unfoldable': False,
                    'level': 3,
                    'columns': cols,
                })
            # Add an empty line after the total to make a space between two currencies
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': '',
                'style': 'border-bottom-style: none',
                'unfoldable': False,
                'level': 0,
                'columns': [{'template': 'account_followup.line_template'} for col in columns],
            })
        # Remove the last empty line
        if lines:
            lines.pop()

        # Catch negative numbers when present
        for line in lines:
            for col in line['columns']:
                if self.env.company.currency_id.compare_amounts(col.get('no_format', 0.0), 0.0) == -1:
                    col['class'] = 'number color-red'

        return lines