# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    request_status = fields.Selection(
        selection_add=[('created_po', 'PO. Created'), ('refused',)],)

    user_status = fields.Selection(
        selection_add=[('created_po', 'Created PO')],
    )

    def action_approve(self, approver=None):
        super(ApprovalRequest, self).action_approve(approver)
        if self.purchase_order_count > 0:
            for request in self:
                approver = request.approver_ids
                if approver:
                    approver.write({'status': 'created_po'})
                request._compute_request_status()

    def action_create_purchase_orders(self):
        super(ApprovalRequest, self).action_create_purchase_orders()

        for request in self:
            approver = request.approver_ids
            if approver:
                approver.write({'status': 'created_po'})
            request._compute_request_status()

    @api.depends('approver_ids.status', 'approver_ids.required')
    def _compute_request_status(self):
        super(ApprovalRequest, self)._compute_request_status()
        for request in self:
            status_lst = request.mapped('approver_ids.status')
            if 'created_po' in status_lst:
                request.request_status = 'created_po'


class ApprovalApproverCustom(models.Model):
    _inherit = 'approval.approver'

    status = fields.Selection(
        selection_add=[('created_po', 'Created PO')],
    )
