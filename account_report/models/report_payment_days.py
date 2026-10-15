# -*- coding: utf-8 -*-

import re
import json
from datetime import datetime

from odoo import fields, models, api, _


class ReportCertificationReport(models.AbstractModel):
    _name = 'reports.assistant_report'
    _description = 'Asistente de reportes'
    _inherit = 'account.report'

    MAX_LINES = 2
    filter_unfold_all = False
    filter_partner = True
    filter_date = {'mode': 'range', 'filter': 'this_year'}

    def _get_bimonth_for_aml(self, aml):
        bimonth = aml.date.month
        # month:   1   2   3   4   5   6   7   8   9   10  11   12
        # bimonth: \ 1 /   \ 2 /   \ 3 /   \ 4 /   \ 5 /    \ 6 /
        bimonth = (bimonth + 1) // 2
        return bimonth

    def _get_bimonth_name(self, bimonth_index):
        bimonth_names = {
            1: 'Enero - Febrero',
            2: 'Marzo - Abril',
            3: 'Mayo - Junio',
            4: 'Julio - Agosto',
            5: 'Septiembre - Octubre',
            6: 'Noviembre - Diciembre',
        }
        return bimonth_names[bimonth_index]

    def _get_domain(self, options):
        common_domain = [
            ('partner_id', '!=', False),
            ('state', 'not in', ('draft', 'cancel')),
            ('move_type', 'in', ('out_invoice',))
        ]
        if options.get('partner_ids'):
            common_domain += [('partner_id.id', 'in',
                               options.get('partner_ids'))]
        if options.get('partner_categories'):
            common_domain += [('partner_id.category_id',
                               'parent_of', options.get('partner_categories'))]
        if options.get('date'):
            common_domain += [('invoice_date', '>=', options['date'].get('date_from')),
                              ('invoice_date', '<=', options['date'].get('date_to'))]
        return common_domain

    def _handle_aml(self, aml, lines_per_bimonth):
        raise NotImplementedError()

    def _get_values_for_columns(self, values):
        raise NotImplementedError()

    def _add_to_partner_total(self, totals, new_values):
        for column, value in new_values.items():
            if isinstance(value, str):
                totals[column] = ''
            else:
                totals[column] = totals.get(column, 0) + value

    def _get_values_for_columns_for_partner_group(self, partner_totals, partner_cols, partner_id, options):
        sales_factured = self.env['sale.order'].search_count([
            ('partner_id', '=', partner_id.id),
            ('invoice_status', '=', 'invoiced')
        ])
        date = '%s / %s' % (
            options['date']['date_from'],
            options['date']['date_to']
        )
        average_transactions = partner_totals['value_sold'] / \
            partner_totals['num_transactions']
        payment_days = partner_totals['days'] / \
            partner_totals['num_transactions']

        out = [
            {'name': partner_id.vat, 'field_name': 'vat'},
            {'name': date, 'field_name': 'date'},
            {'name': sales_factured, 'field_name': 'sales_factured'},
            {'name': self.format_value(
                partner_id.credit_limit or 0), 'field_name': 'credit_limit'},
            partner_cols[4],
            {'name': self.format_value(
                average_transactions), 'field_name': 'value_sold'},
            partner_cols[6],
            {'name': payment_days, 'field_name': 'days'},
        ]

        return out

    def _generate_lines_for_partner(self, partner_id, lines_per_group, options):
        lines = []
        if lines_per_group:
            partner_line = {
                'id': 'partner_%s' % (partner_id.id),
                'partner_id': partner_id.id,
                'name': partner_id.name,
                'level': 2,
                'unfoldable': True,
                'unfolded': 'partner_%s' % (partner_id.id) in options.get('unfolded_lines'),
            }
            lines.append(partner_line)

            partner_totals = {}
            for group, values in lines_per_group.items():
                self._add_to_partner_total(partner_totals, values)
                if 'partner_%s' % (partner_id.id) in options.get('unfolded_lines'):
                    lines.append({
                        'id': 'line_%s_%s' % (partner_id.id, group),
                        'name': '',
                        'unfoldable': False,
                        'columns': self._get_values_for_columns(values),
                        'level': 1,
                        'parent_id': 'partner_%s' % (partner_id.id),
                    })
            partner_line_col = self._get_values_for_columns(partner_totals)
            partner_line_col = self._get_values_for_columns_for_partner_group(
                partner_totals, partner_line_col, partner_id, options)
            partner_line['columns'] = partner_line_col

        return lines

    def _get_lines(self, options, line_id=None):
        lines = []
        domain = []

        domain += self._get_domain(options)

        if line_id:
            partner_id = re.search('partner_(.+)', line_id).group(1)
            if partner_id:
                domain += [('partner_id.id', '=', partner_id)]

        moves = self.env['account.move'].search(domain, order='partner_id, id')
        previous_partner_id = self.env['res.partner']
        lines_per_group = {}

        for move in moves:
            if previous_partner_id != move.partner_id:
                partner_lines = self._generate_lines_for_partner(
                    previous_partner_id, lines_per_group, options)
                if partner_lines:
                    lines += partner_lines
                    lines_per_group = {}
                previous_partner_id = move.partner_id

            self._handle_aml(move, lines_per_group)

        lines += self._generate_lines_for_partner(
            previous_partner_id, lines_per_group, options)

        return lines

    def print_pdf(self, options):
        lines = self._get_lines(options)
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'l10n_co_reports.retention_report.wizard',
            'views': [(self.env.ref('l10n_co_reports.retention_report_wizard_form').id, 'form')],
            'view_id': self.env.ref('l10n_co_reports.retention_report_wizard_form').id,
            'target': 'new',
            'context': {'lines': lines, 'report_name': self._name},
            'data': {'options': json.dumps(options), 'output_format': 'pdf'},
        }


class ReportPaymentDays(models.AbstractModel):
    _name = 'report.payment.days'
    _description = 'Reporte de días de pago'
    _inherit = 'reports.assistant_report'

    def _get_report_name(self):
        return u'Días de Pago'

    def _get_columns_name(self, options):
        return [
            {'name': 'Nombre'},
            {'name': 'NIT'},
            {'name': 'Periodo'},
            {'name': 'N° Pedidos Facturados', 'class': 'number'},
            {'name': 'Cupo de crédito', 'class': 'number'},
            {'name': 'Factura'},
            {'name': 'Valor Vendido', 'class': 'number'},
            {'name': 'Vendedor'},
            {'name': u'Días de pago', 'class': 'number'},

            # {'name': 'N° Transacciones', 'class': 'number'},
        ]

    def _get_values_for_columns(self, values):
        return [
            {'name': values['vat'], 'field_name': 'vat'},
            {'name': values['date'], 'field_name': 'date'},
            {'name': values['sales_factured'], 'field_name': 'sales_factured'},
            {'name': values['credit_limit'], 'field_name': 'credit_limit'},
            {'name': values['move'], 'field_name': 'move'},
            {'name': self.format_value(
                values['value_sold']), 'field_name': 'value_sold'},
            {'name': values['saleperson'], 'field_name': 'saleperson'},
            {'name': values['days'], 'field_name': 'days'}

            # {'name': values['num_transactions'], 'field_name': 'num_transactions'},
        ]

    def _get_domain(self, options):
        res = super(ReportPaymentDays, self)._get_domain(options)
        # res += [('account_id.code', '=like', '2365%'), ('account_id.code', '!=', '236505')]

        return res

    def _handle_aml(self, move, lines_per_move):
        move_name = move.name
        if move_name not in lines_per_move:

            days = self._calculate_payment_days(move)

            lines_per_move[move_name] = {
                'vat': '',
                'date': '',
                'sales_factured': '',
                'credit_limit': '',
                'move': move.display_name,
                'value_sold': 0,
                'saleperson': move.invoice_user_id.display_name,
                'days': days,

                'num_transactions': 0,
            }

        lines_per_move[move_name]['value_sold'] += move.amount_untaxed
        lines_per_move[move_name]['num_transactions'] += 1
        # if move.credit:
        #     lines_per_move[move_name]['tax_base_amount'] += move.tax_base_amount
        # else:
        #     lines_per_move[move_name]['tax_base_amount'] -= move.tax_base_amount

    def _calculate_payment_days(self, move):
        days = 0
        reconcile_info = move._get_reconciled_info_JSON_values()
        if reconcile_info:
            payment_date = reconcile_info[0].get('date', False)
            if payment_date:
                invoice_date = move.date
                days = (payment_date - invoice_date).days
        return days
