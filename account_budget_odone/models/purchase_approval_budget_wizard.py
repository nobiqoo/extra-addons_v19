# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseApprovalBudgetWizard(models.TransientModel):
    _inherit = 'purchase.approval.budget.wizard'

    account_line_id = fields.Many2one(
        comodel_name='account.move',
        string='Factura'
    )
    
    def request_approval_budget(self):
        if self.env.context.get('active_model') == 'account.move': # If it's an invoice
            self.account_line_id.button_request_approval_without_budget()
        else:
            self.order_id.button_request_approval_without_budget()