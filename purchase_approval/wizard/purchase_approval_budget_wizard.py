# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseApprovalBudgetWizard(models.TransientModel):
    _name = 'purchase.approval.budget.wizard'

    order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Orden de compra'
    )
    line_ids = fields.One2many(
        comodel_name='purchase.approval.budget.line.wizard',
        string='Líneas',
        inverse_name='main_wizard_id'
    )

    def request_approval_budget(self):
        self.order_id.button_request_approval_without_budget()