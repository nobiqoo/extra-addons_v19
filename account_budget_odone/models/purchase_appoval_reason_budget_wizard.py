# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseAppovalReasonBudgetWizard(models.TransientModel):
    _inherit = 'purchase.appoval.reason.budget.wizard'

    
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Factura'
    )

    def approva_budget(self):
        if self.env.context.get('actual_model') and self.env.context.get('actual_model') == 'account.move':
            #If it's an invoice
            move = self.move_id
            if self.env.user.id in move.user_approvals_by_budget_am.ids:
                move.reason_approval_by_budget = self.reason_approval_by_budget
                move.message_post(
                    body='Esta factura se ha aprobado por '
                        'falta de presupuesto por la siguiente razón: {reason}'.format(
                            reason=move.reason_approval_by_budget)
                )
                move.approval_by_budget_confirm = True
                move.state = 'draft'
                move.action_post()
        
        else:
            order = self.order_id
            if self.env.user.id in order.user_approvals_by_budget.ids:
                order.reason_approval_by_budget = self.reason_approval_by_budget
                order.message_post(
                    body='Esta orden de compra se ha aprobado por '
                        'falta de presupuesto por la siguiente razón: {reason}'.format(
                            reason=order.reason_approval_by_budget)
                )
                order.approval_by_budget_confirm = True
                if order.approval_config_id.approval_automatic:
                    order.state = 'purchase'
                else:
                    order.state = 'approved'