# -*- coding: utf-8 -*-

from odoo import api, fields, models

SPLIT_METHOD = [
    ('equal', 'Equal'),
    ('by_quantity', 'By Quantity'),
    ('by_current_cost_price', 'By Current Cost'),
    ('by_weight', 'By Weight'),
    ('by_volume', 'By Volume'),
]


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    cost_ids = fields.One2many(
        comodel_name='mrp.production.cost',
        inverse_name='production_id',
        string='Costs',
        copy=False
    )

    cost_id = fields.Many2one(
        comodel_name='stock.landed.cost',
        copy=False
    )

    @api.onchange('bom_id', 'product_id', 'product_qty', 'product_uom_id')
    def _onchange_cost_ids(self):
        if not self.bom_id and not self._origin.product_id:
            return
        if self.product_id != self._origin.product_id:
            self.cost_ids = [(5,)]
        if self.bom_id and self.product_id and self.product_qty > 0:
            list_cost = [(4, cost.id)
                         for cost in self.cost_ids.filtered(lambda m: not m.cost_id)]
            costs_values = self._get_costs_values()
            cost_dict = {cost.cost_id.id: cost for cost in self.cost_ids.filtered(
                lambda m: m.cost_id)}
            for cost_values in costs_values:
                if cost_values['cost_id'] in cost_dict:
                    list_cost += [(1, cost_dict[cost_values['cost_id']].id, cost_values)]
                else:
                    list_cost += [(0, 0, cost_values)]
            self.cost_ids = list_cost
        else:
            self.cost_ids = [(2, cost.id)
                             for cost in self.cost_ids.filtered(lambda m: m.cost_id)]

    def _get_costs_values(self):
        costs = []
        for production in self:
            if not production.bom_id:
                continue
            factor = production.product_uom_id._compute_quantity(
                production.product_qty, production.bom_id.product_uom_id) / production.bom_id.product_qty
            for cost in production.bom_id.cost_ids:
                if production.bom_id.type == 'phantom':
                    continue
                costs.append(
                    {
                        'account_id': cost.account_id and cost.account_id.id or False,
                        'cost_id': cost.id,
                        'price_unit': cost.price_unit * factor,
                        'product_id': cost.product_id and cost.product_id.id or False,
                        # 'production_id': production.id,
                        'split_method': cost.split_method,
                    }
                )
        return costs

    def button_mark_done(self):
        res = super(MrpProduction, self).button_mark_done()
        if res is True:
            self.action_cost_create()
        return res

    def action_cost_create(self):
        # TO DO
        # Account Analytic
        Cost = self.env['stock.landed.cost']
        for production in self.filtered(lambda p: p.product_id.cost_method in ('fifo', 'average')):
            cost_lines = []
            for cost in production.cost_ids:
                cost_lines.append((0, 0, cost.action_cost_prepare()))
            if cost_lines:
                cost_vals = self.action_cost_prepare()
                cost_vals.update({'cost_lines': cost_lines})
                cost = Cost.create(cost_vals)
                cost.button_validate()
                production.cost_id = cost.id

    def action_cost_prepare(self):
        self.ensure_one()
        return {
            'account_journal_id': self.env.ref('mrp_baseline.journal_mrp_cost').id,
            'date': fields.Date.today(),
            'target_model': 'manufacturing',
            'mrp_production_ids': [(4, self.id, 0)],
        }

    def _post_inventory(self, cancel_backorder=False):
        res = super(MrpProduction, self)._post_inventory(
            cancel_backorder=cancel_backorder
        )
        work_center_cost = 0
        finished_move = self.move_finished_ids.filtered(
            lambda x: x.product_id == self.product_id and x.state == 'done' and x.quantity_done > 0
        )
        if finished_move:
            finished_move.ensure_one()
            for work_order in self.workorder_ids:
                time_lines = work_order.time_ids.filtered(
                    lambda x: x.date_end and x.cost_already_recorded
                )
                duration = sum(time_lines.mapped('duration'))
                work_center_cost += (duration / 60.0) * \
                    work_order.workcenter_id.costs_hour
                work_order.account_move_create(finished_move, work_center_cost)
        return res


class MrpProductionCost(models.Model):
    _name = 'mrp.production.cost'
    _description = 'Production Costs'

    account_id = fields.Many2one('account.account')

    cost_id = fields.Many2one('mrp.bom.cost')

    price_unit = fields.Float(digits='Product Price')

    product_id = fields.Many2one(
        comodel_name='product.product',
        domain=[('landed_cost_ok', '=', True)]
    )

    production_id = fields.Many2one(
        comodel_name='mrp.production',
        ondelete='cascade',
        required=True
    )

    split_method = fields.Selection(
        selection=SPLIT_METHOD,
        default='equal'
    )

    def action_cost_prepare(self):
        self.ensure_one()
        return {
            'account_id': self.account_id and self.account_id.id or False,
            'name': self.product_id and self.product_id.name or '',
            'price_unit': self.price_unit,
            'product_id': self.product_id and self.product_id.id or False,
            'split_method': self.split_method
        }
