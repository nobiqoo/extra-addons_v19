# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseApprovalBudgetLineWizard(models.TransientModel):
    _inherit = 'purchase.approval.budget.line.wizard'

    account_line_id = fields.Many2one(
        comodel_name='account.move.line'
    )
    analytic_account_ids = fields.Many2many(
        comodel_name='account.analytic.account',
        string='Cuenta analítica',
        compute='_compute_budget_info',
    )
    crossovered_budget_line_id = fields.Many2one(
        comodel_name='crossovered.budget.lines',
        string='Línea de presupuesto',
        compute='_compute_budget_info',
    )

    def _compute_budget_info(self):
        # Several lines can share the same product, so the analytic account is
        # what lets the user identify which line has no budget available.
        for record in self:
            if record.account_line_id:
                line = record.account_line_id
                budget_line = line.budget_account_line_id
            else:
                line = record.order_line_id
                budget_line = line.crossovered_budget_line_id
            analytic_ids = {
                int(analytic_id)
                for analytic_ids in (line.analytic_distribution or {})
                for analytic_id in analytic_ids.split(',')
            }
            record.analytic_account_ids = self.env['account.analytic.account'].browse(analytic_ids).exists()
            record.crossovered_budget_line_id = budget_line

    def _compute_amount(self):
        for record in self:
            if self.env.context.get('active_model') == 'account.move':
                line = record.account_line_id
                budget_line = line.budget_account_line_id
            else:
                line = record.order_line_id
                budget_line = line.crossovered_budget_line_id

            planned = budget_line.planned_amount
            commited = budget_line.commited_amount
            amount = line.amount_to_budget

            planned_abs = abs(planned)
            commited_abs = abs(commited)
            amount_abs = abs(amount)

            available = planned_abs - commited_abs

            record.amount_required = amount_abs
            record.amount_available = available
            record.amount_difference = amount_abs - available