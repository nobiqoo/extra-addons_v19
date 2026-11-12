# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, _
from odoo.exceptions import UserError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _filter_lot_analytic_lines(self):
        return self.filtered(
            lambda l: not l.display_type
            and l.product_id.type == 'consu'
            and l.company_id.purchase_lot_analytic_control
        )

    def _get_lot_analytic_accounts(self):
        percentages_by_line = {}
        all_account_ids = set()
        for line in self:
            percentages = defaultdict(float)
            for key, percentage in (line.analytic_distribution or {}).items():
                for account_id in key.split(','):
                    percentages[int(account_id)] += percentage
            percentages_by_line[line.id] = percentages
            all_account_ids.update(percentages)

        accounts_by_id = {
            account.id: account
            for account in self.env['account.analytic.account'].browse(all_account_ids).with_context(lang=False)
        }
        empty = self.env['account.analytic.account']
        result = {}
        for line in self:
            plan = line.company_id.purchase_lot_analytic_plan_id
            candidates = {
                account_id: percentage
                for account_id, percentage in percentages_by_line[line.id].items()
                if accounts_by_id[account_id].root_plan_id == plan
            }
            result[line.id] = accounts_by_id[max(candidates, key=candidates.get)] if candidates else empty
        return result

    def _validate_analytic_distribution(self):
        super()._validate_analytic_distribution()
        self._filter_lot_analytic_lines()._check_lot_analytic_requirements()

    def _check_lot_analytic_requirements(self):
        """Valida la cuenta del plan configurado y los lotes archivados antes de confirmar la OC."""
        if not self:
            return
        companies_without_plan = self.company_id.filtered(lambda c: not c.purchase_lot_analytic_plan_id)
        if companies_without_plan:
            raise UserError(_(
                "Configure the analytic plan for lots in Purchase settings of company %s before confirming the order.",
                companies_without_plan[0].name,
            ))
        account_by_line = self._get_lot_analytic_accounts()

        for line in self:
            if not account_by_line[line.id]:
                raise UserError(_(
                    "You must set an analytic account of plan '%(plan)s' on the line for product %(product)s "
                    "before confirming the order.",
                    plan=line.company_id.purchase_lot_analytic_plan_id.name,
                    product=line.product_id.display_name,
                ))

        pairs = {(line.product_id.id, account_by_line[line.id].name) for line in self}
        existing_lots = self.env['stock.lot'].with_context(active_test=False).search([
            '|', ('company_id', '=', False), ('company_id', 'in', self.company_id.ids),
            ('product_id', 'in', [product_id for product_id, _name in pairs]),
            ('name', 'in', list({name for _product_id, name in pairs})),
        ])
        lots_by_key = {(lot.product_id.id, lot.name): lot for lot in existing_lots}

        for line in self:
            key = (line.product_id.id, account_by_line[line.id].name)
            lot = lots_by_key.get(key)
            if lot and not lot.active:
                raise UserError(_(
                    "An archived lot '%(lot)s' already exists for product %(product)s. "
                    "Unarchive the lot or correct the analytic account before confirming the order.",
                    lot=lot.name, product=line.product_id.display_name,
                ))

    def _assign_lot_names_from_analytic_account(self):
        """Crea/completa la línea de operación de recepción con el lote heredado de la cuenta analítica."""
        lines = self._filter_lot_analytic_lines()
        if not lines:
            return
        account_by_line = lines._get_lot_analytic_accounts()
        moves = lines.order_id.picking_ids.move_ids.filtered(
            lambda m: m.purchase_line_id.id in account_by_line and m.state not in ('done', 'cancel')
        )

        moves_without_line = moves.filtered(lambda m: not m.move_line_ids)
        move_line_vals_list = []
        for move in moves_without_line:
            account = account_by_line.get(move.purchase_line_id.id)
            if not account:
                continue
            vals = move._prepare_move_line_vals(quantity=move.product_uom_qty)
            vals['lot_name'] = account.name
            move_line_vals_list.append(vals)
        if move_line_vals_list:
            self.env['stock.move.line'].create(move_line_vals_list)

        existing_without_lot = (moves - moves_without_line).move_line_ids.filtered(
            lambda ml: not ml.lot_id and not ml.lot_name
        )
        move_lines_by_name = defaultdict(lambda: self.env['stock.move.line'])
        for move_line in existing_without_lot:
            account = account_by_line.get(move_line.move_id.purchase_line_id.id)
            if account:
                move_lines_by_name[account.name] |= move_line
        for name, mls in move_lines_by_name.items():
            mls.write({'lot_name': name})
