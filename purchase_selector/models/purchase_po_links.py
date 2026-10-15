# -*- coding: utf-8 -*-
from odoo import fields, models, api, tools
from markupsafe import Markup

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_request_ids = fields.Many2many(
        'approval.request',
        'approval_request_purchase_rel',
        'purchase_id', 'approval_request_id',
        string='Requisiciones origen',
        copy=False
    )

    def action_view_approval_requests(self):
        self.ensure_one()
        action = self.env.ref('approvals.approval_request_action').read()[0]
        action['domain'] = [('id', 'in', self.approval_request_ids.ids)]
        return action
    
    @api.depends('origin', 'approval_request_ids')
    def _compute_origin_document_html(self):
        super()._compute_origin_document_html()
        for order in self:
            if order.approval_request_ids:
                links = ', '.join(
                    (
                        f'<a class="o_form_uri" '
                        f'href="/web#id={req.id}&model=approval.request&view_type=form">'
                        f'{tools.html_escape(req.name)}</a>'
                    )
                    for req in order.approval_request_ids
                )
                order.origin_document_html = Markup(links)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    approval_line_id = fields.Many2one(
        'approval.product.line',
        string='Línea de requisición',
        copy=False,
        index=True
    )
