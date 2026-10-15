# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseApprovalBudgetLineWizard(models.TransientModel):
    _name = 'purchase.approval.budget.line.wizard'

    main_wizard_id = fields.Many2one(
        comodel_name='purchase.approval.budget.wizard'
    )
    order_line_id = fields.Many2one(
        comodel_name='purchase.order.line'
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto'
    )
    amount_required = fields.Float(
        string='Monto Requerido',
        compute='_compute_amount'
    )
    amount_available = fields.Float(
        string='Monto Disponible',
        compute='_compute_amount'
    )
    amount_difference = fields.Float(
        string='Diferencia',
        compute='_compute_amount'
    )

    def _compute_amount(self):
        for record in self:
            record.amount_required = record.order_line_id.amount_to_budget * -1
            record.amount_available = abs(record.order_line_id.budget_line_id.planned_amount - record.order_line_id.budget_line_id.commited_amount)
            record.amount_difference = abs(record.order_line_id.budget_line_id.planned_amount - record.order_line_id.budget_line_id.commited_amount) - abs(record.order_line_id.amount_to_budget)
