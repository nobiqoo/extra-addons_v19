# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    income_ids = fields.One2many('sale.order',
                                 'ticket_id',
                                 'Income',
                                 copy=False)
    expense_ids = fields.One2many('purchase.order',
                                  'ticket_id',
                                  'Expense',
                                  copy=False)
    income_count = fields.Integer('Income count',
                                  compute='_compute_financial_count')
    expense_count = fields.Integer('Expense count',
                                   compute='_compute_financial_count')
    plan_income = fields.Monetary('Planned Income',
                                  currency_field='company_currency_id',
                                  compute='_compute_financial_summary')
    real_income = fields.Monetary('Real Income',
                                  currency_field='company_currency_id',
                                  compute='_compute_financial_summary')
    plan_expense = fields.Monetary('Planned Expense',
                                   currency_field='company_currency_id',
                                   compute='_compute_financial_summary')
    real_expense = fields.Monetary('Real Expense',
                                   currency_field='company_currency_id',
                                   compute='_compute_financial_summary')
    plan_margin = fields.Float('Planned Margin', compute='_compute_margin')
    real_margin = fields.Float('Real Margin', compute='_compute_margin')
    company_currency_id = fields.Many2one(string='Company Currency',
                                          related='company_id.currency_id',)
    helpdesk_ticket_income_expense = fields.Boolean(
        'Income and Expense in helpdesk Tickets',
        related='company_id.helpdesk_ticket_income_expense'
    )

    @api.depends('income_ids', 'expense_ids')
    def _compute_financial_count(self):
        for record in self:
            record.income_count = len(record.income_ids)
            record.expense_count = len(record.expense_ids)

    def action_view_income(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Income',
            'view_mode': 'list,form',
            'res_model': 'sale.order',
            'views': [(self.env.ref('sale.view_quotation_tree').id, 'tree'),
                      (False, 'form')],
            'domain': [('ticket_id', '=', self.id)],
            'target': 'current',
            'context': {
                'create': True,
                'default_ticket_id': self.id,
                'search_default_ticket_id': self.id
            },
        }

    def action_view_expense(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Expense',
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'domain': [('ticket_id', '=', self.id)],
            'target': 'current',
            'context': {
                'create': True,
                'default_ticket_id': self.id,
                'search_default_ticket_id': self.id
            },
        }

    def _compute_financial_summary(self):
        for record in self:
            currency_id = record.company_id.currency_id
            # Income
            plan_income = []
            for order in record.income_ids.filtered(
                    lambda i: i.state != 'cancel'):
                total = record._convert_to_currency(
                    order.amount_untaxed,
                    order.currency_id,
                    currency_id,
                    record.company_id,
                    order.date_order or order.create_date,
                    False
                )
                plan_income.append(total)
            real_income = []
            for order in record.income_ids.filtered(
                lambda i: i.state != 'cancel' and
                    i.invoice_status == 'invoiced'):
                total = record._convert_to_currency(
                    order.amount_untaxed,
                    order.currency_id,
                    currency_id,
                    record.company_id,
                    order.date_order or order.create_date,
                    False
                )
                real_income.append(total)
            record.plan_income = sum(plan_income)
            record.real_income = sum(real_income)
            # Expense
            plan_expense = []
            for order in record.expense_ids.filtered(
                    lambda i: i.state != 'cancel'):
                total = record._convert_to_currency(
                    order.amount_untaxed,
                    order.currency_id,
                    currency_id,
                    record.company_id,
                    order.date_order or order.create_date,
                    False
                )
                plan_expense.append(total)
            real_expense = []
            for order in record.expense_ids.filtered(
                lambda i: i.state != 'cancel' and
                    i.invoice_status == 'invoiced'):
                total = record._convert_to_currency(
                    order.amount_untaxed,
                    order.currency_id,
                    currency_id,
                    record.company_id,
                    order.date_order or order.create_date,
                    False
                )
                real_expense.append(total)
            record.plan_expense = sum(plan_expense)
            record.real_expense = sum(real_expense)

    def _convert_to_currency(self, from_amount, from_currency,
                             to_currency, company, date, trm=False):
        rate = 1
        if from_currency == to_currency:
            rate = 1
        currency_rates = (
            from_currency + to_currency)._get_rates(company, date)
        if trm:
            to_c = 1 / trm
        else:
            to_c = currency_rates.get(to_currency.id)
        rate = to_c / currency_rates.get(from_currency.id)
        return to_currency.round(from_amount * rate)

    def _compute_margin(self):
        for record in self:
            record.plan_margin = (
                (record.plan_income - record.plan_expense) / record.plan_income
            ) if record.plan_income else 0
            record.real_margin = (
                (record.real_income - record.real_expense) / record.real_income
            ) if record.real_income else 0
