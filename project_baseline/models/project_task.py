# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    bl_income_ids = fields.One2many('sale.order',
                                    'bl_task_id',
                                    'Income',
                                    copy=False)
    bl_expense_ids = fields.One2many('purchase.order',
                                     'bl_task_id',
                                     'Expense',
                                     copy=False)
    bl_income_count = fields.Integer('Income count',
                                     compute='_compute_financial_count')
    bl_expense_count = fields.Integer('Expense count',
                                      compute='_compute_financial_count')
    bl_plan_income = fields.Monetary('Planned Income',
                                     currency_field='bl_company_currency_id',
                                     compute='_compute_financial_summary')
    bl_real_income = fields.Monetary('Real Income',
                                     currency_field='bl_company_currency_id',
                                     compute='_compute_financial_summary')
    bl_plan_expense = fields.Monetary('Planned Expense',
                                      currency_field='bl_company_currency_id',
                                      compute='_compute_financial_summary')
    bl_real_expense = fields.Monetary('Real Expense',
                                      currency_field='bl_company_currency_id',
                                      compute='_compute_financial_summary')
    bl_plan_margin = fields.Float('Planned Margin', compute='_compute_margin')
    bl_real_margin = fields.Float('Real Margin', compute='_compute_margin')
    bl_company_currency_id = fields.Many2one(string='Company Currency',
                                             related='company_id.currency_id',)
    project_task_income_expense = fields.Boolean(
        'Income and expense in project tasks',
        related='company_id.project_task_income_expense'
    )

    @api.depends('bl_income_ids', 'bl_expense_ids')
    def _compute_financial_count(self):
        for record in self:
            record.bl_income_count = len(record.bl_income_ids)
            record.bl_expense_count = len(record.bl_expense_ids)

    def action_view_income(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Income',
            'view_mode': 'list,form',
            'res_model': 'sale.order',
            'views': [(self.env.ref('sale.view_quotation_tree').id, 'tree'),
                      (False, 'form')],
            'domain': [('bl_task_id', '=', self.id)],
            'target': 'current',
            'context': {
                'create': True,
                'default_bl_task_id': self.id,
                'search_default_bl_task_id': self.id
            },
        }

    def action_view_expense(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Expense',
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'domain': [('bl_task_id', '=', self.id)],
            'target': 'current',
            'context': {
                'create': True,
                'default_bl_task_id': self.id,
                'search_default_bl_task_id': self.id
            },
        }

    def _compute_financial_summary(self):
        for record in self:
            fin_data = record._get_financial_summary()

            record.bl_plan_income = fin_data.get('plan_income', 0)
            record.bl_real_income = fin_data.get('real_income', 0)
            record.bl_plan_expense = fin_data.get('plan_expense', 0)
            record.bl_real_expense = fin_data.get('real_expense', 0)

    def _get_financial_summary(self):
        self.ensure_one()
        fin_data = self._get_income_and_expense_from_task()
        if self.child_ids:
            for child in self.child_ids:
                child_data = child._get_financial_summary()
                fin_data['plan_income'] += child_data['plan_income']
                fin_data['real_income'] += child_data['real_income']
                fin_data['plan_expense'] += child_data['plan_expense']
                fin_data['real_expense'] += child_data['real_expense']
        return fin_data

    def _get_income_and_expense_from_task(self):
        self.ensure_one()
        currency_id = self.company_id.currency_id
        # Income
        plan_income = []
        for order in self.bl_income_ids.filtered(
                lambda i: i.state != 'cancel'):
            total = self._convert_to_currency(
                order.amount_untaxed,
                order.currency_id,
                currency_id,
                self.company_id,
                order.date_order or order.create_date,
                False
            )
            plan_income.append(total)
        real_income = []
        for order in self.bl_income_ids.filtered(
            lambda i: i.state != 'cancel' and
                i.invoice_status == 'invoiced'):
            total = self._convert_to_currency(
                order.amount_untaxed,
                order.currency_id,
                currency_id,
                self.company_id,
                order.date_order or order.create_date,
                False
            )
            real_income.append(total)

        # Expense
        plan_expense = []
        for order in self.bl_expense_ids.filtered(
                lambda i: i.state != 'cancel'):
            total = self._convert_to_currency(
                order.amount_untaxed,
                order.currency_id,
                currency_id,
                self.company_id,
                order.date_order or order.create_date,
                False
            )
            plan_expense.append(total)
        real_expense = []
        for order in self.bl_expense_ids.filtered(
            lambda i: i.state != 'cancel' and
                i.invoice_status == 'invoiced'):
            total = self._convert_to_currency(
                order.amount_untaxed,
                order.currency_id,
                currency_id,
                self.company_id,
                order.date_order or order.create_date,
                False
            )
            real_expense.append(total)
        return {
            'plan_income': sum(plan_income),
            'real_income': sum(real_income),
            'plan_expense': sum(plan_expense),
            'real_expense': sum(real_expense)
        }

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
            record.bl_plan_margin = (
                (record.bl_plan_income - record.bl_plan_expense) /
                record.bl_plan_income
            ) if record.bl_plan_income else 0
            record.bl_real_margin = (
                (record.bl_real_income - record.bl_real_expense) /
                record.bl_real_income
            ) if record.bl_real_income else 0
