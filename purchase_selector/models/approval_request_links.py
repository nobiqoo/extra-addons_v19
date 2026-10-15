# -*- coding: utf-8 -*-
from odoo import fields, models

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    purchase_order_ids = fields.Many2many(
        'purchase.order',
        'approval_request_purchase_rel',  
        'approval_request_id',            
        'purchase_id',                    
        string='Órdenes de compra',
        copy=False,
    )
    purchase_order_count = fields.Integer(
        string='N° OCs', compute='_compute_purchase_order_count'
    )

    def _compute_purchase_order_count(self):
        for r in self:
            r.purchase_order_count = len(r.purchase_order_ids)

    def action_view_purchase_orders(self):
        self.ensure_one()
        action = self.env.ref('purchase.purchase_rfq').read()[0]
        action['domain'] = [('id', 'in', self.purchase_order_ids.ids)]
        return action
