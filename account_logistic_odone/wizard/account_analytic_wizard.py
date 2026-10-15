# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountAnalyticWizard(models.TransientModel):
    _name = 'account.analytic.wizard'
    _description = 'Account analytic wizard'

    account_accounts_ids = fields.Many2many('account.account')
    analytic_accounts_ids = fields.Many2many('account.analytic.account')

    date_start = fields.Date('Start date')
    date_end = fields.Date('End date')

    range_id = fields.Many2one('date.range')

    @api.onchange('range_id')
    def _onchange_range_id(self):
        if self.range_id:
            self.date_start = self.range_id.date_start
            self.date_end = self.range_id.date_end

    def generate_report(self):
        self.ensure_one()
        data = self.prepare_data()
        report_type = self.env.context.get('report_type') or 'xlsx'
        if report_type == 'xlsx':
            report_name = 'account_logistic_odone.report_account_analytic_xlsx'
        report = self.env.ref(report_name)
        return report.report_action(self, data=data)

    def prepare_data(self):
        self.ensure_one()

        Account = self.env['account.analytic.account']
        Line = self.env['account.move.line']

        company_id = self.env.company.id
        accounts = self.analytic_accounts_ids
        if not accounts:
            accounts = Account.search([
                ('company_id', 'in', [company_id, False])
            ])

        account_data = []
        for account in accounts:
            line_data = []
            line_domain = [
                ('date', '>=', self.date_start),
                ('date', '<=', self.date_end),
                ('analytic_line_ids.account_id', '=', account.id),
                ('company_id', '=', company_id),
            ]
            if self.account_accounts_ids:
                line_domain.append(
                    ('account_id', 'in', self.account_accounts_ids.ids)
                )
            line_moves = Line.search(line_domain)
            lines = line_moves.analytic_line_ids.filtered(
                lambda l: l.account_id.id == account.id)
            for line in lines:
                move = line.move_line_id
                line_vals = {
                    'id': line.id,
                    'move_id': move and move.id or False,
                    'move': move and move.move_id.name or '',
                    'date': move and move.date or False,
                    'partner': move and move.partner_id.name or False,
                    'debit': move and move.debit or 0.0,
                    'credit': move and move.credit or 0.0,
                    'price': move and move.price_subtotal or 0.0,
                    'amount': line.amount,
                    'name': move and move.name or '',
                    'currency': move and move.move_id.currency_id.name or '',
                    'rate': move and move.move_id.current_exchange_rate or 0.0,
                }
                line_data.append(line_vals)

            moves = lines.move_line_id.move_id
            lines_origin = moves.filtered(lambda m: m.origin)
            lines_destination = moves.filtered(lambda m: m.destination)
            lines_motor = moves.filtered(lambda m: m.motor_ship)

            account_vals = {
                'id': account.id,
                'name': account.name,
                'origin': lines_origin and lines_origin[0].origin or '',
                'destination': lines_destination and lines_destination[0].destination or '',
                'motor': lines_motor and lines_motor[0].motor_ship or '',
                'line_ids': line_data,
            }
            account_data.append(account_vals)

        data = {'account_ids': account_data}
        return data
