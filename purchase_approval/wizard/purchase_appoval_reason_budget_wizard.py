# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseAppovalReasonBudgetWizard(models.TransientModel):
    _name = 'purchase.appoval.reason.budget.wizard'
    
    order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Orden de Compra'
    )
    reason_approval_by_budget = fields.Char(
        string='Razón de Aprobación'
    )

    def approva_budget(self):
        order = self.order_id
        if self.env.user.id in order.user_approvals_by_budget.ids:
            order.reason_approval_by_budget = self.reason_approval_by_budget
            order.message_post(
                body='Esta orden de compra se ha aprobado por '
                     'falta de presupuesto por la siguiente razón: {reason}'.format(
                        reason=order.reason_approval_by_budget)
            )
            order._action_done_approval_activity(
                "Confirmar la orden de compra por falta de presupuesto"
            )
            order.approval_by_budget_confirm = True
            if order.approval_config_id.approval_automatic:
                order.state = 'purchase'
            else:
                order.state = 'approved'
