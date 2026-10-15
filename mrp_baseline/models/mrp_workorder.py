# -*- coding: utf-8 -*-

from odoo import fields, models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    def _prepare_analytic_line_values(self, account, unit_amount, amount):
        values = super(MrpWorkorder, self)._prepare_analytic_line_values(
            account, unit_amount, amount)
        values.update({'mrp_workorder_id': self.id})
        return values

    def account_move_create(self, move, cost):
        self.ensure_one()
        Move = self.env['account.move']
        if not self.workcenter_id.costs_hour_account_account_id:
            return False
        move_vals = self.account_move_prepare(move, cost)
        move = Move.create(move_vals)
        move.action_post()
        return move

    def account_move_prepare(self, move, cost):
        self.ensure_one()
        journal_id, acc_src, acc_dest, acc_valuation = move._get_accounting_data_for_valuation()
        date = self._context.get(
            'force_period_date', fields.Date.context_today(self)
        )
        description = '%s - %s' % (move.reference, move.product_id.name)
        move_lines = self.account_move_line_prepare(
            move, cost, description, acc_src
        )
        vals = {
            'journal_id': journal_id,
            'line_ids': move_lines,
            'date': date,
            'ref': description,
            # 'stock_move_id': self.id,
            # 'stock_valuation_layer_ids': [(6, None, [svl_id])],
            'move_type': 'entry',
        }
        return vals

    def account_move_line_prepare(self, move, cost, description, account):
        self.ensure_one()
        debit_vals = {
            'name': description,
            'product_id': move.product_id.id,
            'quantity': move.quantity_done,
            'product_uom_id': move.product_id.uom_id.id,
            'ref': description,
            # 'partner_id': self.env.company.partner_id.id,
            'debit': cost,
            'credit': 0,
            'account_id': account,
        }
        credit_vals = {
            'name': description,
            'product_id': move.product_id.id,
            'quantity': move.quantity_done,
            'product_uom_id': move.product_id.uom_id.id,
            'ref': description,
            # 'partner_id': self.env.company.partner_id.id,
            'debit': 0,
            'credit': cost,
            'account_id': self.workcenter_id.costs_hour_account_account_id.id,
        }
        # Analytic
        account_anlytic_line = self.account_anlytic_line_search()
        if account_anlytic_line:
            credit_vals.update({
                'analytic_line_ids': [(4, account_anlytic_line.id, 0)],
                # TO DO
                # No create analytic
                # 'analytic_account_id': account_anlytic_line.account_id.id
            })
        return [(0, 0, debit_vals), (0, 0, credit_vals)]

    def account_anlytic_line_search(self):
        self.ensure_one()
        Line = self.env['account.analytic.line']
        domain = [('mrp_workorder_id', '=', self.id)]
        return Line.search(domain, limit=1)

    def _get_duration_expected(self, alternative_workcenter=False, ratio=1):
        if self.operation_id and self.operation_id.is_fixed_time:
            return self.operation_id.time_cycle
        else:
            return super(MrpWorkorder, self)._get_duration_expected(alternative_workcenter, ratio)
